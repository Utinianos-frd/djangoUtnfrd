Writing Tests Skill
Overview
Esta skill guía cómo escribir tests unitarios/de integración que realmente protejan contra regresiones, en vez de tests que solo suben un número de cobertura. Un buen test documenta el comportamiento esperado y falla exactamente cuando ese comportamiento se rompe — ni antes, ni después.
Testear comportamiento (qué hace el sistema desde afuera), no implementación (cómo lo hace por dentro). Un test que se rompe al refactorizar sin cambiar comportamiento es un test mal diseñado.
The Writing Tests Workflow
Identificar el contrato público de la unidad bajo test — qué entra, qué sale, qué efectos secundarios importan
Cubrir el camino feliz primero — el caso de uso principal, con un assert claro del resultado esperado
Cubrir casos borde y de error, uno por test — permisos denegados, input inválido, valores límite (vacío, cero, máximo), estados inconsistentes
Preferir arrange-act-assert — setup claro, una acción bajo test, aserciones enfocadas en lo que ese test verifica
Usar fixtures/factories para el setup repetido, en vez de copiar y pegar la misma inicialización en cada test
Nombrar el test por el comportamiento esperado, no por el método que llama (ej. test_rechaza_rol_invalido, no test_cambiar_rol_2)
Aislar cada test — nada de depender del orden de ejecución ni de estado dejado por otro test; usar transacciones/rollback o fixtures frescos
Process Flow
El siguiente diagrama es el procedimiento autoritativo para escribir un test nuevo.

flowchart TD
    subgraph Fase1["Fase 1: Entender qué se testea"]
        Contract["Identificar el contrato público: input, output, efectos secundarios"]
    end
    subgraph Fase2["Fase 2: Casos a cubrir"]
        Happy["Camino feliz: caso de uso principal"]
        Edge["Casos borde: límites, vacío, inválido"]
        Perm["Casos de permiso/autorización si aplica"]
    end
    subgraph Fase3["Fase 3: Escritura"]
        Arrange["Arrange: setup mínimo necesario, vía fixtures"]
        Act["Act: una sola acción bajo test"]
        Assert["Assert: aserciones enfocadas en el comportamiento, no en detalles internos"]
    end
    subgraph Fase4["Fase 4: Verificación"]
        RunFail{"¿El test falla si se rompe el comportamiento a propósito?"}
    end

    Contract --> Happy --> Edge --> Perm --> Arrange --> Act --> Assert --> RunFail
    RunFail -->|"No falla (falso negativo)"| Arrange
    RunFail -->|"Falla correctamente"| Done(["Test listo"])
Principios
Un test, un comportamiento — si el nombre del test necesita "y" para describirlo, probablemente son dos tests.
Los tests de permisos importan tanto como los de lógica — en cualquier sistema con roles, cada acción restringida necesita al menos un test que confirme que el rol equivocado es rechazado.
Nada de sleep ni dependencias de timing real — si hace falta simular tiempo, mockear el reloj, no esperar de verdad.
Los tests son documentación — alguien que nunca vio el código debería poder entender el comportamiento esperado leyendo los nombres de los tests de un archivo.
Limpieza automática sobre limpieza manual — preferir mecanismos que revierten solos (transacciones, fixtures con scope) antes que teardown escrito a mano.
No testear el framework — no hace falta un test que confirme que Django guarda un campo en la base de datos; sí hace falta uno que confirme la regla de negocio construida sobre eso.
