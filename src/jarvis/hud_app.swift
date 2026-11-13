// Jarvis window: one long-running floating panel at the top of the screen. It is two things:
//  1. A listening pill (top centre). Option+Space (env JARVIS_HOTKEY, e.g. "cmd+shift+j") starts
//     recording to a 16 kHz mono WAV and shows a live waveform; the hotkey again stops, Esc cancels.
//  2. The fly-in HUD (top right) with the live DAG and log of the running task. The pill morphs into it.
// Reads one JSON object per line on stdin:
//   {"heard": "text"}   the transcript (empty string: nothing was understood)
//   {"notice": "text"}  show text in the window and fade it (a question, no module fits)
//   {"idle": true}      the task ended: hide the HUD in a moment
//   {"debug": "press"}  act as the hotkey ("escape" acts as Esc), for tests without a keyboard
//   {"dismiss": true}   hide now
//   anything else       the task state from hud.py `snapshot`
// Prints one JSON object per line on stdout:
//   {"event":"recorded","wav":"/path"}, {"event":"cancelled"}, {"event":"ready"|"error","text":"..."}
// When stdin closes the window fades out and exits.
// Build: swiftc -O -o bin/jarvis-hud src/jarvis/hud_app.swift

import AppKit
import AVFoundation
import Carbon.HIToolbox
import Foundation

let WIDTH: CGFloat = 360
let MARGIN: CGFloat = 16
let PAD: CGFloat = 14
let PILL_W: CGFloat = 380
let PILL_H: CGFloat = 48
let PILL_RADIUS: CGFloat = 24
let HUD_RADIUS: CGFloat = 14
let BARS = 36
let ICONS = ["done": "✓", "running": "●", "waiting": "○", "failed": "✗", "gate": "?"]
// Explicit light colors: the window is always dark, and semantic colors such as
// tertiaryLabelColor can resolve to the light-mode (near-black) value in the text view.
let TITLE = NSColor.white
let BODY = NSColor(white: 1.0, alpha: 0.85)
let DIM = NSColor(white: 1.0, alpha: 0.65)
let COLORS: [String: NSColor] = [
    "done": .systemGreen, "running": .systemBlue, "waiting": DIM,
    "failed": .systemRed, "gate": .systemOrange,
]

func emit(_ object: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: object),
          let line = String(data: data, encoding: .utf8) else { return }
    print(line)
    fflush(stdout)
}

func ease(_ t: CGFloat) -> CGFloat { t < 0.5 ? 4 * t * t * t : 1 - pow(-2 * t + 2, 3) / 2 }
func backOut(_ t: CGFloat) -> CGFloat { let c1: CGFloat = 1.70158; return 1 + (c1 + 1) * pow(t - 1, 3) + c1 * pow(t - 1, 2) }
func lerp(_ a: CGFloat, _ b: CGFloat, _ t: CGFloat) -> CGFloat { a + (b - a) * t }
func lerpRect(_ a: NSRect, _ b: NSRect, _ t: CGFloat) -> NSRect {
    NSRect(x: lerp(a.minX, b.minX, t), y: lerp(a.minY, b.minY, t), width: lerp(a.width, b.width, t), height: lerp(a.height, b.height, t))
}

// MARK: hotkey

// Key codes for the keys JARVIS_HOTKEY may name (ANSI layout), and its modifiers.
let KEYS: [String: UInt32] = [
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12, "w": 13,
    "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "9": 25, "7": 26,
    "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46, "space": 49,
]
let MODS: [String: UInt32] = [
    "option": UInt32(optionKey), "alt": UInt32(optionKey), "cmd": UInt32(cmdKey), "command": UInt32(cmdKey),
    "ctrl": UInt32(controlKey), "control": UInt32(controlKey), "shift": UInt32(shiftKey),
]

/// "option+space" -> key code and modifiers. A modifier is required so a plain key is never stolen.
func parseHotkey(_ spec: String) -> (key: UInt32, mods: UInt32)? {
    var mods: UInt32 = 0
    var key: UInt32?
    for part in spec.lowercased().split(separator: "+").map({ $0.trimmingCharacters(in: .whitespaces) }) {
        if let m = MODS[part] { mods |= m } else if let k = KEYS[part], key == nil { key = k } else { return nil }
    }
    guard let key = key, mods != 0 else { return nil }
    return (key, mods)
}

func registerHotKey(id: UInt32, key: UInt32, mods: UInt32) -> EventHotKeyRef? {
    var ref: EventHotKeyRef?
    let status = RegisterEventHotKey(key, mods, EventHotKeyID(signature: 0x4A52_5653, id: id),
                                     GetApplicationEventTarget(), 0, &ref)
    return status == noErr ? ref : nil
}

func installHotKeyHandler() {
    var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
    InstallEventHandler(GetApplicationEventTarget(), { _, event, _ -> OSStatus in
        var id = EventHotKeyID()
        GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID),
                          nil, MemoryLayout<EventHotKeyID>.size, nil, &id)
        DispatchQueue.main.async { if id.id == 1 { window.toggle() } else { window.escape() } }
        return noErr
    }, 1, &spec, nil, nil)
}

// MARK: the pill's contents

final class PillView: NSView {
    enum Kind { case listening, transcribing, message }
    var kind = Kind.listening
    var message = ""
    var levels = [CGFloat](repeating: 0, count: BARS)
    var phase: CGFloat = 0

    override func draw(_ dirty: NSRect) {
        let cy = bounds.height / 2
        if kind == .message {
            text(message, size: 14, weight: .medium, color: TITLE, x: 20, width: bounds.width - 40)
            return
        }
        if kind == .listening {  // a pulsing red dot
            NSColor.systemRed.withAlphaComponent(0.55 + 0.45 * (sin(phase * 5) + 1) / 2).setFill()
            NSBezierPath(ovalIn: NSRect(x: 20, y: cy - 5, width: 10, height: 10)).fill()
        }
        for i in 0..<BARS {
            let level = kind == .listening ? levels[i] : 0.22 + 0.18 * sin(phase * 7 - CGFloat(i) * 0.45)  // ripple while transcribing
            let height = max(3, level * (bounds.height - 16))
            NSColor(white: 1, alpha: 0.3 + 0.65 * CGFloat(i) / CGFloat(BARS - 1)).setFill()
            NSBezierPath(roundedRect: NSRect(x: 44 + CGFloat(i) * 5.5, y: cy - height / 2, width: 3, height: height),
                         xRadius: 1.5, yRadius: 1.5).fill()
        }
        text(kind == .listening ? "Listening" : "Transcribing…", size: 12, weight: .medium, color: DIM,
             x: 256, width: bounds.width - 256 - 16)
    }

    func text(_ s: String, size: CGFloat, weight: NSFont.Weight, color: NSColor, x: CGFloat, width: CGFloat) {
        let style = NSMutableParagraphStyle()
        style.lineBreakMode = .byTruncatingTail
        let str = NSAttributedString(string: s, attributes: [
            .font: NSFont.systemFont(ofSize: size, weight: weight), .foregroundColor: color, .paragraphStyle: style])
        let h = str.size().height
        str.draw(in: NSRect(x: x, y: (bounds.height - h) / 2, width: width, height: h))
    }
}

// MARK: the window

enum Mode { case hidden, listening, transcribing, heard, message, hud }

final class Window {
    let panel: NSPanel
    let box = NSVisualEffectView()
    let text = NSTextView()
    let pill = PillView()
    var mode = Mode.hidden
    var hudHeight: CGFloat = 80
    var anim: Timer?
    var pillTimer: Timer?
    var laterItem: DispatchWorkItem?
    var recorder: AVAudioRecorder?
    var recordURL: URL?
    var escRef: EventHotKeyRef?
    var smooth: CGFloat = 0
    var ticks = 0
    var latest: [String: Any]?  // the newest task state
    var taskActive = false
    var heardText = ""
    var holdOver = false
    var afterHold: (() -> Void)?
    var morphing = false

    init() {
        panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: WIDTH, height: 120),
                        styleMask: [.borderless, .nonactivatingPanel, .utilityWindow],
                        backing: .buffered, defer: false)
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        panel.isMovableByWindowBackground = true
        panel.appearance = NSAppearance(named: .darkAqua)

        box.frame = panel.contentView!.bounds
        box.material = .hudWindow
        box.blendingMode = .behindWindow
        box.state = .active
        box.wantsLayer = true
        box.layer?.cornerRadius = HUD_RADIUS
        box.layer?.masksToBounds = true
        box.autoresizingMask = [.width, .height]
        panel.contentView?.addSubview(box)

        text.isEditable = false
        text.isSelectable = false
        text.drawsBackground = false
        text.textContainerInset = NSSize(width: PAD, height: PAD)
        text.textContainer?.lineFragmentPadding = 0
        text.textContainer?.widthTracksTextView = true
        box.addSubview(text)
        pill.isHidden = true
        box.addSubview(pill)
    }

    // MARK: helpers

    /// Run `step` with progress 0...1 over `seconds`, then `done`. A new animation replaces the running one.
    /// (NSAnimationContext never completes for a non-activating accessory panel, so a timer drives the motion.)
    func animate(_ seconds: Double, step: @escaping (CGFloat) -> Void, done: @escaping () -> Void = {}) {
        anim?.invalidate()
        let frames = max(1, Int(seconds * 60))
        var i = 0
        let timer = Timer(timeInterval: seconds / Double(frames), repeats: true) { timer in
            i += 1
            step(CGFloat(i) / CGFloat(frames))
            if i >= frames { timer.invalidate(); done() }
        }
        RunLoop.main.add(timer, forMode: .common)
        anim = timer
    }

    /// Run `f` after `seconds`; a newer call replaces it.
    func later(_ seconds: Double, _ f: @escaping () -> Void) {
        laterItem?.cancel()
        let item = DispatchWorkItem(block: f)
        laterItem = item
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: item)
    }

    func screen() -> NSRect {
        let s = NSScreen.screens.first { NSMouseInRect(NSEvent.mouseLocation, $0.frame, false) } ?? NSScreen.main
        return s?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
    }

    func pillFrame() -> NSRect {
        let s = screen()
        return NSRect(x: s.midX - PILL_W / 2, y: s.maxY - PILL_H - 10, width: PILL_W, height: PILL_H)
    }

    func hudFrame() -> NSRect {
        let s = screen()
        return NSRect(x: s.maxX - WIDTH - MARGIN, y: s.maxY - hudHeight - MARGIN, width: WIDTH, height: hudHeight)
    }

    /// Both contents stay pinned to the top of the box and keep their own size, so a morph never reflows them.
    func setFrame(_ r: NSRect) {
        panel.setFrame(r, display: true)
        let b = box.bounds
        pill.frame = NSRect(x: 0, y: b.height - PILL_H, width: PILL_W, height: PILL_H)
        text.frame = NSRect(x: 0, y: b.height - hudHeight, width: WIDTH, height: hudHeight)
    }

    func setRadius(_ r: CGFloat) {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        box.layer?.cornerRadius = r
        CATransaction.commit()
    }

    // MARK: pill states

    func startPillTimer() {
        pillTimer?.invalidate()
        let timer = Timer(timeInterval: 1.0 / 60, repeats: true) { [unowned self] t in
            guard self.mode == .listening || self.mode == .transcribing else { t.invalidate(); return }
            self.pill.phase += 1.0 / 60
            if let r = self.recorder {
                r.updateMeters()
                self.smooth = max(min(1, max(0, (CGFloat(r.averagePower(forChannel: 0)) + 55) / 45)), self.smooth * 0.85)
                self.ticks += 1
                if self.ticks % 2 == 0 { self.pill.levels.removeFirst(); self.pill.levels.append(self.smooth) }
            }
            self.pill.needsDisplay = true
        }
        RunLoop.main.add(timer, forMode: .common)
        pillTimer = timer
    }

    /// Bring the pill on screen: it drops in from the top, or the HUD shrinks back into it.
    func showPill() {
        let target = pillFrame()
        pill.isHidden = false
        pill.alphaValue = 1
        if mode == .hud && panel.isVisible {
            let from = panel.frame
            animate(0.35, step: { t in
                let e = ease(t)
                self.setFrame(lerpRect(from, target, e))
                self.setRadius(lerp(HUD_RADIUS, PILL_RADIUS, e))
                self.text.alphaValue = 1 - min(1, t * 2.5)
                self.pill.alphaValue = max(0, min(1, (t - 0.4) / 0.5))
            }, done: { self.text.isHidden = true; self.text.alphaValue = 1; self.pill.alphaValue = 1 })
        } else if mode == .listening || mode == .transcribing || mode == .heard || mode == .message {
            return  // the pill is already there
        } else {
            text.isHidden = true
            setRadius(PILL_RADIUS)
            setFrame(target.offsetBy(dx: 0, dy: 40))
            panel.alphaValue = 0
            panel.orderFrontRegardless()
            animate(0.38, step: { t in  // a springy drop from the top edge
                self.panel.alphaValue = min(1, t * 3)
                self.setFrame(target.offsetBy(dx: 0, dy: 40 * (1 - backOut(t))))
            })
        }
    }

    /// A short line in the pill, then fade away.
    func flash(_ message: String, hold: Double = 2.5) {
        showPill()
        mode = .message
        heardText = ""
        pill.kind = .message
        pill.message = message
        pill.needsDisplay = true
        later(hold) { self.hide(then: self.restoreTask) }
    }

    func hide(then: @escaping () -> Void = {}) {
        mode = .hidden
        let from = panel.frame
        animate(0.3, step: { t in
            self.panel.alphaValue = 1 - t
            self.panel.setFrame(from.offsetBy(dx: 0, dy: 14 * t), display: true)
        }, done: { self.panel.orderOut(nil); self.panel.alphaValue = 1; then() })
    }

    func restoreTask() {
        if taskActive, let s = latest { showHUD(s) }
    }

    // MARK: hotkey, recording

    func toggle() {
        switch mode {
        case .hidden, .hud, .message: startListening()
        case .listening: stopListening()
        default: break  // transcribing or showing the transcript: ignore
        }
    }

    func escape() { if mode == .listening { cancelListening() } }

    func debug(_ what: String) { if what == "press" { toggle() } else if what == "escape" { escape() } }

    func startListening() {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized: beginRecording()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { ok in
                DispatchQueue.main.async { if ok { self.beginRecording() } else { self.denied() } }
            }
        default: denied()
        }
    }

    func denied() {
        emit(["event": "error", "text": "microphone access is off: allow your terminal in System Settings > Privacy > Microphone"])
        flash("Microphone access is off", hold: 3)
    }

    func beginRecording() {
        laterItem?.cancel()
        afterHold = nil
        escRef = registerHotKey(id: 2, key: 53, mods: 0)  // Esc cancels, but only while listening
        smooth = 0
        pill.levels = [CGFloat](repeating: 0, count: BARS)
        pill.kind = .listening
        showPill()
        mode = .listening
        startPillTimer()
        // CoreAudio can take about a second to start the first time: do it off the main thread so the pill moves meanwhile.
        let url = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("jarvis-\(UUID().uuidString).wav")
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM), AVSampleRateKey: 16000.0, AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16, AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false,
        ]
        DispatchQueue.global().async {
            let r = try? AVAudioRecorder(url: url, settings: settings)
            r?.isMeteringEnabled = true
            let ok = r?.record() ?? false
            DispatchQueue.main.async {
                guard ok, let r = r else { return self.failed() }
                if self.mode == .listening {
                    self.recorder = r
                    self.recordURL = url
                } else {  // cancelled before the microphone was ready
                    r.stop()
                    try? FileManager.default.removeItem(at: url)
                }
            }
        }
    }

    func failed() {
        if let ref = escRef { UnregisterEventHotKey(ref); escRef = nil }
        emit(["event": "error", "text": "could not start the microphone"])
        flash("Could not start the microphone")
    }

    func finishRecording() -> (URL, Double)? {
        guard let r = recorder, let url = recordURL else { return nil }
        let seconds = r.currentTime
        r.stop()
        recorder = nil
        recordURL = nil
        if let ref = escRef { UnregisterEventHotKey(ref); escRef = nil }
        return (url, seconds)
    }

    func stopListening() {
        guard let (url, seconds) = finishRecording() else { return }
        if seconds < 0.4 {
            try? FileManager.default.removeItem(at: url)
            emit(["event": "cancelled"])
            return flash("Too short")
        }
        mode = .transcribing
        pill.kind = .transcribing
        emit(["event": "recorded", "wav": url.path])
    }

    func cancelListening() {
        if let (url, _) = finishRecording() { try? FileManager.default.removeItem(at: url) }
        emit(["event": "cancelled"])
        hide(then: restoreTask)
    }

    // MARK: messages from Python

    func onHeard(_ words: String) {
        guard mode == .transcribing else { return }
        if words.isEmpty { return flash("Didn't catch that", hold: 1.8) }
        heardText = words
        holdOver = false
        afterHold = nil
        pill.kind = .message
        pill.message = words
        pill.needsDisplay = true
        mode = .heard
        // Show the transcript for a second, then follow whatever Python did with it.
        later(1.0) {
            self.holdOver = true
            if let go = self.afterHold { self.afterHold = nil; go() } else { self.later(6) { self.hide(then: self.restoreTask) } }
        }
    }

    func afterTranscript(_ go: @escaping () -> Void) {
        if holdOver { go() } else { afterHold = go }
    }

    func onNotice(_ message: String) {
        guard mode == .heard, !message.isEmpty else { return }
        afterTranscript {
            self.morphToHUD(["module": "", "request": message, "nodes": [], "log": []])
            self.later(4) { self.hide(then: self.restoreTask) }
        }
    }

    func onIdle() {
        taskActive = false
        if mode == .hud { later(2.5) { self.hide() } }
    }

    func onState(_ state: [String: Any]) {
        latest = state
        taskActive = true
        switch mode {
        case .hidden, .hud:
            laterItem?.cancel()
            showHUD(state)
        case .heard:  // the task started by what was just said: the pill becomes its HUD
            if !heardText.isEmpty, (state["request"] as? String ?? "").contains(heardText) {
                afterTranscript { if let s = self.latest { self.morphToHUD(s) } }
            }
        default: break  // listening, transcribing or a message: shown again when the pill goes
        }
    }

    // MARK: the HUD

    /// Put the state into the text view; return nothing, but keep `hudHeight` right.
    func prepareHUD(_ state: [String: Any]) {
        text.setFrameSize(NSSize(width: WIDTH, height: text.frame.height))
        text.textStorage?.setAttributedString(render(state))
        text.layoutManager?.ensureLayout(for: text.textContainer!)
        let used = text.layoutManager!.usedRect(for: text.textContainer!).height + 2 * PAD
        hudHeight = min(max(used, 80), screen().height - 2 * MARGIN)
    }

    func showHUD(_ state: [String: Any]) {
        prepareHUD(state)
        if morphing { return }  // the morph reads the new height on its next frame
        if mode == .hud && panel.isVisible {
            setFrame(hudFrame())
            return
        }
        mode = .hud
        pill.isHidden = true
        text.isHidden = false
        text.alphaValue = 1
        setRadius(HUD_RADIUS)
        let target = hudFrame()
        let slide = WIDTH + MARGIN  // slide in from the right edge
        setFrame(target.offsetBy(dx: slide, dy: 0))
        panel.alphaValue = 0
        panel.orderFrontRegardless()
        animate(0.25) { t in
            self.panel.alphaValue = t
            self.setFrame(target.offsetBy(dx: slide * (1 - t), dy: 0))
        }
    }

    /// The pill grows into the HUD: frame, corner radius and content cross-fade together.
    func morphToHUD(_ state: [String: Any]) {
        prepareHUD(state)
        let from = panel.frame
        let radius = box.layer?.cornerRadius ?? PILL_RADIUS
        mode = .hud
        morphing = true
        text.isHidden = false
        text.alphaValue = 0
        animate(0.5, step: { t in
            let e = ease(t)
            self.setFrame(lerpRect(from, self.hudFrame(), e))
            self.setRadius(lerp(radius, HUD_RADIUS, e))
            self.pill.alphaValue = 1 - min(1, t * 2.5)
            self.text.alphaValue = max(0, min(1, (t - 0.35) / 0.5))
        }, done: {
            self.morphing = false
            self.pill.isHidden = true
            self.pill.alphaValue = 1
            self.text.alphaValue = 1
            self.panel.invalidateShadow()
        })
    }

    func render(_ s: [String: Any]) -> NSAttributedString {
        let out = NSMutableAttributedString()
        func line(_ str: String, _ font: NSFont, _ color: NSColor) {
            out.append(NSAttributedString(string: str + "\n", attributes: [.font: font, .foregroundColor: color]))
        }
        let module = s["module"] as? String ?? ""
        let request = s["request"] as? String ?? ""
        line(module.isEmpty ? "Jarvis" : "Jarvis · \(module)", .boldSystemFont(ofSize: 13), TITLE)
        if !request.isEmpty {
            line(request.replacingOccurrences(of: "\n", with: " "), .systemFont(ofSize: 11), BODY)
        }
        let mono = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        let nodes = s["nodes"] as? [[String: Any]] ?? []
        if !nodes.isEmpty { line("", .systemFont(ofSize: 4), .clear) }
        for n in nodes {
            let status = n["status"] as? String ?? "waiting"
            let note = n["note"] as? String ?? ""
            let id = n["id"] as? String ?? "?"
            line("\(ICONS[status] ?? "○") \(id)" + (note.isEmpty ? "" : "  \(note)"), mono,
                 COLORS[status] ?? BODY)
        }
        let logs = s["log"] as? [String] ?? []
        if !logs.isEmpty { line("", .systemFont(ofSize: 4), .clear) }
        for entry in logs {
            line(entry, NSFont.monospacedSystemFont(ofSize: 10, weight: .regular), DIM)
        }
        if out.length > 0 { out.deleteCharacters(in: NSRange(location: out.length - 1, length: 1)) }
        return out
    }

    /// stdin closed: Jarvis is gone. Stop recording, fade out, exit.
    func finish() {
        if let (url, _) = finishRecording() { try? FileManager.default.removeItem(at: url) }
        if !panel.isVisible { exit(0) }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { self.hide { exit(0) } }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)  // no Dock icon, never takes focus
let window = Window()

installHotKeyHandler()
let wanted = ProcessInfo.processInfo.environment["JARVIS_HOTKEY"] ?? "option+space"
var chosen = wanted
var combo = parseHotkey(wanted)
if combo == nil {
    emit(["event": "error", "text": "JARVIS_HOTKEY \"\(wanted)\" is not understood; using option+space"])
    chosen = "option+space"
    combo = parseHotkey(chosen)
}
if let combo = combo, registerHotKey(id: 1, key: combo.key, mods: combo.mods) != nil {
    emit(["event": "ready", "text": "press \(chosen) to speak"])
} else {
    emit(["event": "error", "text": "hotkey \(chosen) could not be registered; another app may use it"])
}

DispatchQueue.global().async {
    while let raw = readLine() {
        guard let data = raw.data(using: .utf8),
              let msg = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { continue }
        DispatchQueue.main.async {
            if let what = msg["debug"] as? String { window.debug(what) }
            else if msg["dismiss"] as? Bool == true { window.hide() }
            else if let words = msg["heard"] as? String { window.onHeard(words) }
            else if let words = msg["notice"] as? String { window.onNotice(words) }
            else if msg["idle"] as? Bool == true { window.onIdle() }
            else { window.onState(msg) }
        }
    }
    DispatchQueue.main.async { window.finish() }
}

app.run()
