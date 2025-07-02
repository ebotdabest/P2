# P2 aka PTO aka Python To Object

Unfortunately PTO doesn't mean Paid Time Off, but rather Python To Object
The point is to create a language that feels similar in synthax and experience to python, but make it useable in a C ABI setting
This would enable a python like synthax to be usable in low-level settings on a whole new level
P2 aims to deliver this.
While some features were either modified or removed it remains really close to python

## P2 is not a language
While yes on a technicality it is one, it doesn't have a standard library like most language
Since P2's only goal it to turn most python code into object files, to be linked etc it only has basic python functions HOWEVER it does come with
classes, and every python function / feature that doesn't need the `import` keyword
