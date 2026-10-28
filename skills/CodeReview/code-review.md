Code Review Skill
Overview
Esta skill guía una revisión de código sistemática, enfocada en encontrar bugs reales (no preferencias de estilo) antes de que un cambio se mergee: errores de lógica, casos borde no contemplados, problemas de seguridad, y oportunidades de simplificación.
No reportar como hallazgo nada que no se haya verificado leyendo el código real. Un falso positivo cuesta más confianza que el valor de diez hallazgos verdaderos.
The Code Review Workflow
Entender la intención del cambio — qué problema resuelve, no solo qué líneas tocó
Leer el diff con contexto — abrir el archivo completo alrededor de cada cambio, no solo las líneas marcadas
Buscar bugs de corrección — lógica, casos borde (null/None, vacío, límites, concurrencia), manejo de errores
Buscar problemas de seguridad — inyección, falta de validación de permisos, secretos expuestos, datos de usuario sin sanitizar
Buscar simplificación — código duplicado, abstracciones innecesarias, código muerto
Verificar cada hallazgo antes de reportarlo — releer el código citado, confirmar que el escenario de falla es real
Reportar ordenado por severidad, con archivo:línea y el escenario concreto que falla
Process Flow
El siguiente diagrama es el procedimiento autoritativo. Ejecutar los pasos en el orden mostrado.

flowchart TD
    subgraph Fase1["Fase 1: Contexto"]
        Intent["Entender qué problema resuelve el cambio"]
        Read["Leer el diff con el archivo completo como contexto"]
    end
    subgraph Fase2["Fase 2: Búsqueda de hallazgos"]
        Correctness["Bugs de corrección: lógica, casos borde, errores"]
        Security["Problemas de seguridad: inyección, auth, secretos"]
        Simplify["Oportunidades de simplificación"]
    end
    subgraph Fase3["Fase 3: Verificación y reporte"]
        Verify{"¿El hallazgo se confirma releyendo el código real?"}
        Report["Reportar: archivo:línea + escenario concreto, ordenado por severidad"]
    end

    Intent --> Read --> Correctness --> Security --> Simplify --> Verify
    Verify -->|"No se confirma"| Discard(["Descartar, no reportar"])
    Verify -->|"Se confirma"| Report
Principios
No nitpickear estilo salvo que se pida explícitamente — el foco es bugs, no preferencias.
Severidad primero — un bug de seguridad o de corrección pesa más que diez mejoras cosméticas.
Ser específico — "esto podría fallar" sin un escenario concreto no es un hallazgo útil.
Preferir pocos hallazgos verificados a muchos hallazgos dudosos.
No reescribir el código del autor en la revisión — señalar el problema y, si corresponde, sugerir la dirección de la solución, no imponerla.
Revisar también lo que falta — ¿hay un caso de test que debería existir y no está? ¿Falta manejo de un error esperable?
