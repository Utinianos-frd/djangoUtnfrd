Commit Messages Skill
Overview
Esta skill guía cómo escribir mensajes de commit y descripciones de PR que le sirvan a alguien dentro de seis meses, que no tiene el contexto que vos tenés ahora. El diff ya muestra QUÉ cambió línea por línea — el mensaje tiene que explicar POR QUÉ, información que el diff no puede dar por sí solo.
Si el mensaje de commit se puede deducir completamente leyendo el diff, no está agregando valor.
The Commit Messages Workflow
Resumir el cambio en el asunto — modo imperativo ("agrega", "corrige", "elimina"), menos de 70 caracteres, sin punto final
Explicar el POR QUÉ en el cuerpo — qué problema motivó el cambio, qué alternativa se descartó y por qué, qué incidente o decisión lo originó
Referenciar el ticket/issue si existe, pero no como reemplazo de la explicación — un número de ticket sin contexto no ayuda a quien lee el log sin acceso a ese sistema
Para un PR: además del mensaje de commit, un plan de pruebas — qué se probó y cómo, para que quien revisa sepa qué falta verificar
Evitar palabras vacías de contexto — "arreglos varios", "cambios", "updates" no le sirven a nadie que busque en el historial
Process Flow
El siguiente diagrama es el procedimiento autoritativo para escribir un mensaje de commit.

flowchart TD
    Start(["Cambio listo para commitear"]) --> Subject["Asunto: imperativo, <70 caracteres, qué cambia"]
    Subject --> Why{"¿El por qué es obvio solo con el asunto?"}
    Why -->|"Sí (cambio trivial)"| Done(["Commit"])
    Why -->|"No"| Body["Cuerpo: motivación, alternativas descartadas, contexto del incidente/decisión"]
    Body --> Ticket{"¿Existe un ticket/issue relacionado?"}
    Ticket -->|"Sí"| Ref["Referenciarlo, sin que reemplace la explicación en texto"]
    Ticket -->|"No"| Done
    Ref --> Done
Principios
El diff dice QUÉ, el mensaje dice POR QUÉ — nunca repetir en el mensaje lo que ya es obvio mirando el diff.
Un commit, un cambio lógico — si el mensaje necesita "y además" para describirlo, considerar si debería ser dos commits.
Modo imperativo en el asunto — "agrega validación", no "agregando validación" ni "agregué validación".
Pensar en el lector futuro sin contexto — no en el compañero de equipo que ya sabe de qué se está hablando hoy.
Para decisiones no obvias, documentar qué se descartó y por qué — eso es lo que evita que alguien reintente la misma opción seis meses después y tropiece con el mismo problema.
