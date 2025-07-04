# P2 (also called PTO, short for Python To Object)

No, PTO is not Paid Time Off.  
It stands for Python To Object. This is a compiled language that looks and feels like Python, but produces real object files ready for use in low level systems.

P2 is built to bring Python-style syntax into environments where Python normally cannot go. It compiles your code into C ABI compatible object files. That means you can link it into a kernel, call it from C or C++, or embed it into anything that expects native code.

The language keeps what works from Python. It keeps the syntax and structure you know, while removing or rewriting the parts that do not make sense for static compilation or system level programming.

### What P2 Offers

- Compiles to object files using LLVM
- Works directly with the C ABI
- Has no runtime unless you choose one
- Requires type hints and uses static types only
- Feels like Python but gives you full control
- Lets you choose between no standard library, a minimal one, or a full one

P2 is not a scripting language pretending to be something else.  
It is a system language with Python roots, meant for places Python was never meant to reach.


## P2 is not a language
While P2 is technically its own language, it does not include a standard library in the traditional sense. P2's goal is to turn Python-like code into object files that can be linked into larger projects. Because of that, it only supports core language features and a small set of built-in functions.

It does include classes and most native Python functions that do not require an `import` statement. Features like `zip`, `range`, `any`, and `max` etc are available, but anything that would normally come from a module must be linked in separately or provided by the P2 standard layers.
