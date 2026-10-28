Debugging Skill
Overview
Esta skill guía un proceso sistemático para diagnosticar bugs, en vez de probar cambios al azar hasta que algo funcione. El objetivo es encontrar la causa raíz y arreglarla, no silenciar el síntoma.
Nunca declarar un bug resuelto sin haber reproducido el problema primero y confirmado que el fix lo hace desaparecer. "Probé algo y el error dejó de aparecer" no es lo mismo que "entendí por qué pasaba".
The Debugging Workflow
Reproducir el problema de forma confiable — si no se puede reproducir, no se puede confirmar que está arreglado
Leer el error completo — stack trace entero, no solo la última línea; el mensaje casi siempre dice más de lo que parece a primera vista
Formular una hipótesis concreta de la causa, basada en evidencia (el error, los logs, el código), no en una corazonada
Verificar la hipótesis con el mínimo cambio posible — un log, un breakpoint, un assert — antes de tocar código de producción
Si la hipótesis es incorrecta, descartarla y volver al paso 3 con la nueva evidencia — no acumular cambios especulativos
Una vez confirmada la causa raíz, arreglarla ahí, no en el síntoma más visible
Agregar un test de regresión que falle sin el fix y pase con él
Process Flow
El siguiente diagrama es el procedimiento autoritativo para diagnosticar un bug.

flowchart TD
    Start(["Bug reportado"]) --> Repro{"¿Se puede reproducir de forma confiable?"}
    Repro -->|"No"| GetMore["Pedir más contexto: pasos exactos, datos, entorno"]
    GetMore --> Repro
    Repro -->|"Sí"| ReadError["Leer el error/stack trace completo"]
    ReadError --> Hypothesis["Formular una hipótesis concreta de la causa"]
    Hypothesis --> Verify["Verificar con el mínimo cambio posible (log/breakpoint/assert)"]
    Verify --> Confirmed{"¿La evidencia confirma la hipótesis?"}
    Confirmed -->|"No"| Hypothesis
    Confirmed -->|"Sí"| RootFix["Arreglar la causa raíz, no el síntoma"]
    RootFix --> Regression["Agregar un test que falle sin el fix y pase con él"]
    Regression --> Done(["Bug cerrado"])
Principios
Reproducir antes de arreglar — un fix que "parece" funcionar sin reproducción confiable es una apuesta, no una solución.
Un cambio a la vez — cambiar múltiples cosas en simultáneo hace imposible saber cuál arregló (o rompió) algo.
La evidencia manda sobre la intuición — si los logs contradicen la hipótesis, la hipótesis está mal, no los logs.
Bisección antes que inspección lineal — en un bug que "antes andaba", acotar con git bisect o binary search es casi siempre más rápido que leer todo el código de punta a punta.
El síntoma más visible no siempre es la causa — un error en el módulo A puede originarse en datos corruptos que escribió el módulo B mucho antes.
Documentar la causa raíz al cerrar — el mensaje de commit o el comentario debe explicar por qué pasaba, no solo qué línea cambió.
