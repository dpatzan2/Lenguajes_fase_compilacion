Proyecto: Generador de Lexer (YALEX)
===================================

Este proyecto implementa un **generador de analizadores léxicos** a partir de archivos de especificación tipo `.yal` (similar a YALEX / flex).


Estructura inicial
------------------

- `examples/example.yal`: especificación de ejemplo del lexer.
- `examples/input.txt`: archivo de entrada de ejemplo a tokenizar.

Requisitos
----------

- Python 3.10+ (recomendado)

Uso 
-------------

```bash
python yalex_gen.py examples/example.yal -o lexer.py
python lexer.py examples/input.txt
```

Autores
-------

- Diego Patzan 23525 
- Ihan Marroquin 23108
