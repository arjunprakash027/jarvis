"""All text the router sends to Jev or says to Arjun. Edit wording here only."""

WHICH_MODULE = "Which module does the user want to use for `request`?"
A_MODULE_FITS = "Does `request` ask for something that one of the `modules` can do?"
ENOUGH_DETAIL = "Does `request` give enough detail to start the work?"
ENOUGH_DETAIL_YES = (
    "The request names what to do. A follow-up that builds on earlier work "
    "also counts, because the module remembers its earlier requests."
)
ENOUGH_DETAIL_NO = "The request does not say what to do, or it leaves out something the work needs."
LONG_TASK = "Does `request` need more than about 10 steps?"

# What Arjun hears or reads when the router cannot pick a module.
ASK_WHICH = "Is this {a} or {b}?"
ASK_DETAIL = "I need more detail. What exactly should I do?"
SAY_NO_FIT = "No module can do that yet."
