# P2 (Python To Object, not Paid Time Off)

P2 is a compiled language with Python-like syntax, designed for low-level systems where Python can't go. It produces C ABI-compatible object files, linkable with kernels, C/C++ code, or embedded systems.

## Why P2?

P2 retains Python’s familiar syntax but adapts it for static compilation and system-level programming, stripping away features unsuitable for these contexts.

### Key Features

- **Compiles to object files** via LLVM
- **C ABI compatible** for seamless integration
- **No runtime** by default (optional minimal or full runtime)
- **Static typing** with mandatory type hints
- **Python-like feel** with full control
- **Flexible standard library**: none, minimal, or full

## Not a Traditional Language

P2 isn’t a scripting language. It focuses on core language features and a small set of built-in functions (`zip`, `range`, `any`, `max`, etc.). Classes are supported, but module-based features require separate linking or P2’s standard layers.

P2 bridges Python’s simplicity with the power of system-level programming.
