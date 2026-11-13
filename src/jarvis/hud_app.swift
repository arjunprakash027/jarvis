// Jarvis fly-in HUD: a floating, non-activating panel in the top-right corner of the screen.
// It reads one JSON object per line on stdin (see hud.py `snapshot`) and redraws on each.
// When stdin closes, or a line contains {"dismiss": true}, it fades out and exits.
// Build: swiftc -O -o bin/jarvis-hud src/jarvis/hud_app.swift

import AppKit
import Foundation

let WIDTH: CGFloat = 360
let MARGIN: CGFloat = 16
let PAD: CGFloat = 14
let ICONS = ["done": "✓", "running": "●", "waiting": "○", "failed": "✗", "gate": "?"]
let COLORS: [String: NSColor] = [
    "done": .systemGreen, "running": .systemBlue, "waiting": .tertiaryLabelColor,
    "failed": .systemRed, "gate": .systemOrange,
]

final class HUD {
    let panel: NSPanel
    let text = NSTextView()
    var dismissing = false

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

        let box = NSVisualEffectView(frame: panel.contentView!.bounds)
        box.material = .hudWindow
        box.blendingMode = .behindWindow
        box.state = .active
        box.wantsLayer = true
        box.layer?.cornerRadius = 14
        box.layer?.masksToBounds = true
        box.autoresizingMask = [.width, .height]
        panel.contentView?.addSubview(box)

        text.isEditable = false
        text.isSelectable = false
        text.drawsBackground = false
        text.textContainerInset = NSSize(width: PAD, height: PAD)
        text.textContainer?.lineFragmentPadding = 0
        text.textContainer?.widthTracksTextView = true
        text.autoresizingMask = [.width, .height]
        text.frame = box.bounds
        box.addSubview(text)
    }

    func show(_ state: [String: Any]) {
        text.textStorage?.setAttributedString(render(state))
        text.layoutManager?.ensureLayout(for: text.textContainer!)
        let used = text.layoutManager!.usedRect(for: text.textContainer!).height + 2 * PAD
        let height = min(max(used, 80), (NSScreen.main?.visibleFrame.height ?? 800) - 2 * MARGIN)
        let target = frame(height: height)
        if !panel.isVisible {
            let slide = WIDTH + MARGIN  // slide in from the right edge
            panel.setFrame(target.offsetBy(dx: slide, dy: 0), display: false)
            panel.alphaValue = 0
            panel.orderFrontRegardless()
            tween(0.25) { t in
                self.panel.alphaValue = t
                self.panel.setFrame(target.offsetBy(dx: slide * (1 - t), dy: 0), display: true)
            }
        } else {
            panel.setFrame(target, display: true)
        }
    }

    /// Run `step` with progress 0...1 over `seconds`, then `done`. (NSAnimationContext never
    /// completes for a non-activating accessory panel, so a plain timer drives the motion.)
    func tween(_ seconds: Double, step: @escaping (CGFloat) -> Void, done: @escaping () -> Void = {}) {
        let frames = max(1, Int(seconds * 60))
        var i = 0
        let timer = Timer(timeInterval: seconds / Double(frames), repeats: true) { timer in
            i += 1
            step(CGFloat(min(i, frames)) / CGFloat(frames))
            if i >= frames { timer.invalidate(); done() }
        }
        RunLoop.main.add(timer, forMode: .common)
    }

    func frame(height: CGFloat) -> NSRect {
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        return NSRect(x: screen.maxX - WIDTH - MARGIN, y: screen.maxY - height - MARGIN, width: WIDTH, height: height)
    }

    func render(_ s: [String: Any]) -> NSAttributedString {
        let out = NSMutableAttributedString()
        func line(_ str: String, _ font: NSFont, _ color: NSColor) {
            out.append(NSAttributedString(string: str + "\n", attributes: [.font: font, .foregroundColor: color]))
        }
        let module = s["module"] as? String ?? ""
        let request = s["request"] as? String ?? ""
        line(module.isEmpty ? "Jarvis" : "Jarvis · \(module)", .boldSystemFont(ofSize: 13), .labelColor)
        if !request.isEmpty {
            line(request.replacingOccurrences(of: "\n", with: " "), .systemFont(ofSize: 11), .secondaryLabelColor)
        }
        let mono = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        let nodes = s["nodes"] as? [[String: Any]] ?? []
        if !nodes.isEmpty { line("", .systemFont(ofSize: 4), .clear) }
        for n in nodes {
            let status = n["status"] as? String ?? "waiting"
            let note = n["note"] as? String ?? ""
            let id = n["id"] as? String ?? "?"
            line("\(ICONS[status] ?? "○") \(id)" + (note.isEmpty ? "" : "  \(note)"), mono,
                 COLORS[status] ?? .labelColor)
        }
        let logs = s["log"] as? [String] ?? []
        if !logs.isEmpty { line("", .systemFont(ofSize: 4), .clear) }
        for entry in logs {
            line(entry, NSFont.monospacedSystemFont(ofSize: 10, weight: .light), .tertiaryLabelColor)
        }
        if out.length > 0 { out.deleteCharacters(in: NSRange(location: out.length - 1, length: 1)) }
        return out
    }

    func dismiss(after delay: Double) {
        if dismissing { return }
        dismissing = true
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            self.tween(0.4, step: { t in self.panel.alphaValue = 1 - t }, done: { exit(0) })
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)  // no Dock icon, never takes focus
let hud = HUD()

DispatchQueue.global().async {
    while let raw = readLine() {
        guard let data = raw.data(using: .utf8),
              let state = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { continue }
        DispatchQueue.main.async {
            if state["dismiss"] as? Bool == true { hud.dismiss(after: 0) } else { hud.show(state) }
        }
    }
    DispatchQueue.main.async { hud.dismiss(after: 2.5) }  // stdin closed: the task is over
}

app.run()
