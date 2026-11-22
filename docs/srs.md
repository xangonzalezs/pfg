# PFG Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de la técnica en ejercicios posturales

## Especificación de requisitos de software

**Versión:** 2.0
**Fecha:** 22/11/2026

Este documento reúne la especificación de requisitos de software (SRS) del PFG Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de la técnica en ejercicios posturales


## Índice

1. [Descripción general](#1-descripción-general)
2. [Objetivos de negocio](#2-objetivos-de-negocio)
3. [Actores](#3-actores)
4. [Requisitos de usuario](#4-requisitos-de-usuario)
5. [Requisitos funcionales](#5-requisitos-funcionales)
6. [Requisitos no funcionales](#6-requisitos-no-funcionales)
7. [Reglas de negocio](#7-reglas-de-negocio)
8. [Casos de uso](#8-casos-de-uso)
9. [Trazabilidad con los marcos de referencia](#9-trazabilidad-con-los-marcos-de-referencia)



## 1. Descripción general
HandstandApp es una aplicación de escritorio para el aprendizaje del pino
(*handstand*). Estima la postura del atleta a partir de la imagen de una
cámara, detecta las desviaciones técnicas respecto a unos umbrales de
referencia y entrega correcciones por voz mientras el atleta sostiene la
posición. Al terminar la práctica muestra un resumen con el detalle técnico de cada error registrado.

El sistema parte de dos constataciones. La primera es que el pino es un
ejercicio de alto riesgo biomecánico en el que el practicante no puede verse así mismo ni recibir corrección mientras ejecuta, de modo que depende de supervisión presencial continua. La segunda es que los rangos articulares
considerados correctos no son los mismos para todas las personas, por lo que
una referencia única resulta insuficiente. De ahí los dos rasgos que
caracterizan al sistema:

- **Calibración corporal por atleta.** Antes de practicar, cada atleta      captura su postura neutra en vista lateral y frontal. De esas medidas se derivan sus umbrales personalizados. La calibración queda pendiente hasta que un entrenador la revisa y la valida, pudiendo ajustar manualmente los umbrales propuestos. Mientras tanto el atleta puede practicar, pero con umbrales genéricos y con un aviso visible de que no está en modo personalizado.
- **Feedback correctivo auditivo en tiempo real.** El canal es la voz, no la
  pantalla, porque durante el ejercicio el atleta no puede mirarla. Las
  correcciones son locuciones cortas y concretas, se emiten de una en una por prioridad y sin solapamiento. El sistema avisa también cuando no puede evaluar la postura, para que el silencio no se interprete como una ejecución correcta.



> **Nota sobre la numeración.** Los identificadores se asignan en el momento de su definición y no se reordenan posteriormente, para que las referencias,cruzadas permanezcan estables. Por ello la numeración no sigue necesariamente el orden de presentación en las tablas.

---

## 2. Objetivos de negocio
Justifican el porqué del sistema propuesto. Se derivan del estudio exploratorio
con usuarios potenciales, del análisis del sistema previo y del estado del arte.

| ID | Objetivo de negocio |
|---|---|
| OB-01 | Reducir la dependencia de supervisión presencial continua. |
| OB-02 | Proporcionar feedback correctivo inmediato en ausencia de supervisión presencial, en un ejercicio de alto riesgo biomecánico. |
| OB-03 | Personalizar el entrenamiento a la anatomía y nivel de cada usuario. |
| OB-04 | Generar una base de datos de progreso longitudinal del practicante. |
| OB-05 | Habilitar un modelo de supervisión remota para entrenadores profesionales. |

---

## 3. Actores

## 4. Requisitos de usuario
### Rol Usuario

Requisitos comunes a todos los roles.

| ID | Requisito de usuario |
|---|---|
| UR-01 | Debe poder iniciar sesión para acceder a las funcionalidades del sistema |
| UR-02 | Debe poder gestionar su perfil |

### Rol Atleta

| ID | Requisito de usuario |
|---|---|
| UR-03 | Debe poder registrarse creando una nueva cuenta. |
| UR-04 | Debe poder realizar una calibración corporal obligatoria, que quedará pendiente de validación. |
| UR-05 | Debe poder consultar el estado de su calibración |
| UR-06 | Debe poder practicar con la calibración pendiente en modo no personalizado, con una alerta visible en pantalla |
| UR-07 | Debe poder practicar con sus umbrales personalizados tras validarse su calibración |
| UR-08 | Debe poder recibir feedback sonoro en tiempo real durante su práctica |
| UR-09 | Debe poder seleccionar la vista de cámara con la que va a entrenar: lateral o frontal. |
| UR-10 | Debe poder consultar el resumen de cada sesión |
| UR-11 | Debe poder consultar su histórico de progreso |
| UR-12 | Debe poder solicitar una recalibración |
| UR-13 | Debe poder ver y aceptar los ejercicios propuestos por su entrenador |
| UR-14 | Debe poder consultar la información pública de su entrenador asignado |
| UR-15 | Debe poder solicitar un cambio de entrenador |
| UR-28 | Debe poder analizar un vídeo grabado previamente en lugar de utilizar la cámara en directo. |

### Rol Entrenador

| ID | Requisito de usuario |
|---|---|
| UR-16 | Debe poder ver las calibraciones pendientes con las imágenes de la pose neutra capturadas |
| UR-17 | Debe poder seleccionar atletas de un listado para entrenarlos |
| UR-18 | Debe poder validar la calibración de sus atletas ajustando sus umbrales personalizados |
| UR-19 | Debe poder revisar las sesiones de sus atletas con detalle técnico |
| UR-20 | Debe poder consultar los patrones de error de sus atletas a lo largo del tiempo |
| UR-21 | Debe poder introducir ejercicios correctivos a un banco de ejercicios etiquetados según tipo de error |
| UR-22 | Debe poder asignar ejercicios correctivos a sus atletas según sus errores y calibración |
| UR-23 | Debe poder gestionar su información profesional |

### Rol Administrador

| ID | Requisito de usuario |
|---|---|
| UR-24 | Debe poder gestionar cuentas de los usuarios |
| UR-25 | Debe poder asignar atletas a entrenadores |
| UR-26 | Debe poder auditar validaciones de entrenadores |
| UR-27 | Debe poder gestionar el banco de ejercicios correctivos |

---

## 5. Requisitos funcionales
Se derivan de los requisitos de usuario. La primera columna indica el UR del
que procede cada uno, de modo que la tabla es a la vez la matriz de
trazabilidad UR → FR.

| UR origen | ID | Requisito funcional |
|---|---|---|
| UR-01 | FR-001 | El sistema debe permitir autenticar por usuario y contraseña restringiendo cada vista según el rol. |
| UR-02 | FR-002 | El sistema debe permitir modificar datos personales y foto de perfil de usuario. |
| UR-03 | FR-003 | El sistema debe permitir crear cuentas con rol atleta desde el registro público, sin selector de rol. |
| UR-04 | FR-004 | El sistema debe exigir una calibración obligatoria guiada, almacenando las imágenes capturadas para su validación. |
| UR-05 | FR-005 | El sistema debe mostrar el estado de la calibración de cada atleta (sin calibrar, pendiente, validada, rechazada) |
| UR-06 | FR-006 | El sistema debe permitir practicar el ejercicio con umbrales genéricos. |
| UR-06 | FR-007 | El sistema debe mostrar un aviso persistente durante la práctica con umbrales genéricos. |
| UR-07 | FR-008 | El sistema debe actualizar los umbrales personalizados para cada atleta obtenidos de la calibración |
| UR-08 | FR-009 | El sistema debe detectar el pino y analizar su alineación y estabilidad en tiempo real |
| UR-08 | FR-010 | El sistema debe emitir feedback sonoro (mensajes de voz cortos correctivos) con comportamiento de entrenador |
| UR-08 | FR-011 | El sistema debe indicar al usuario de forma perceptible cuándo no puede evaluar la postura, de modo que la ausencia de feedback correctivo no se interprete como una ejecución correcta. |
| UR-08 | FR-012 | El sistema debe utilizar un catálogo único de mensajes (JSON) como fuente de texto y audio |
| UR-09 | FR-013 | El sistema debe permitir al atleta seleccionar la vista de la cámara en la cual desea iniciar la sesión de entrenamiento. |
| UR-09 | FR-014 | El sistema debe avisar al atleta con una alerta sonora si la cámara no se encuentra en buena posición para el análisis. |
| UR-10 | FR-015 | El sistema debe registrar por cada error su tipo, valor medido, umbral e instante |
| UR-10 | FR-016 | El sistema debe mostrar un resumen de sesión con el detalle técnico de cada error |
| UR-11 | FR-017 | El sistema debe mostrar al atleta el histórico y su panel de progreso |
| UR-12 | FR-018 | El sistema debe permitir al atleta solicitar una recalibración, manteniendo la última validada mientras tanto. |
| UR-13 | FR-019 | El sistema debe permitir al atleta ver y aceptar o rechazar ejercicios propuestos por su entrenador |
| UR-13 | FR-020 | El sistema debe permitir la comunicación textual entre atleta y entrenador relativa a cada ejercicio correctivo propuesto |
| UR-14 | FR-021 | El sistema debe permitir al atleta acceder a la información pública de su entrenador asignado. |
| UR-15 | FR-022 | El sistema debe permitir al atleta solicitar a la administración un cambio de entrenador. |
| UR-16 | FR-023 | El sistema debe mostrar al entrenador la cola de calibraciones pendientes de sus atletas con imágenes y umbrales propuestos. |
| UR-17 | FR-024 | El sistema debe permitir al entrenador consultar el listado de atletas sin entrenador asignado e incorporarlos a su cartera. |
| UR-18 | FR-025 | El sistema debe permitir al entrenador ajustar manualmente los umbrales personalizados propuestos. |
| UR-19 | FR-026 | El sistema debe permitir al entrenador revisar las sesiones de sus atletas con el detalle técnico de cada error. |
| UR-20 | FR-027 | El sistema debe mostrar al entrenador patrones de error agregados por atleta en una ventana de sesiones |
| UR-21 | FR-028 | El sistema debe permitir al entrenador introducir ejercicios correctivos al banco de recursos, etiquetados por tipo de error. |
| UR-22 | FR-029 | El sistema debe permitir al entrenador asignar a sus atletas ejercicios correctivos existentes en el banco de ejercicios. |
| UR-23 | FR-030 | El sistema debe permitir al entrenador editar su información profesional y su foto |
| UR-24 | FR-031 | El sistema debe permitir crear el rol de administrador mediante un procedimiento externo a la interfaz de la aplicación. |
| UR-24 | FR-032 | El sistema debe permitir al administrador gestionar (CRUD) cuentas de atleta y entrenador. |
| UR-25 | FR-033 | El sistema debe permitir al administrador asignar atletas a entrenadores |
| UR-26 | FR-034 | El sistema debe registrar cada validación de calibración realizada por un entrenador, junto con su marca temporal. |
| UR-26 | FR-035 | El sistema debe registrar cada ejercicio propuesto por un entrenador a un atleta, junto con su marca temporal. |
| UR-26 | FR-036 | El sistema debe permitir al administrador obtener y mostrar el histórico de actividad de cada entrenador. |
| UR-27 | FR-037 | El sistema debe permitir al administrador gestionar (editar, eliminar u organizar) los ejercicios contenidos en el banco de ejercicios. |
| UR-28 | FR-038 | El sistema debe permitir seleccionar un archivo de vídeo local como fuente de la sesión en sustitución de la cámara, y ejecutar sobre él el mismo análisis y la misma generación de feedback. |
| UR-28 | FR-039 | El sistema debe indicar de forma visible durante todo el análisis de un vídeo que la fuente no es la cámara y que la sesión no quedará registrada. |

---

## 6. Requisitos no funcionales
Se distinguen tres tipos —atributos de calidad, restricciones e interfaces
externas—, clasificación habitual en ingeniería de requisitos (Sommerville,
2011); los atributos de calidad se etiquetan además según las características
del modelo de calidad de ISO/IEC 25010 (ISO/IEC, 2011).

La columna de verificación indica el método previsto para comprobar cada
requisito, y es la que relaciona estos requisitos con el capítulo de pruebas.

| ID | Categoría | Requisito no funcional | Verificación |
|---|---|---|---|
| NFR-01 | Rendimiento | El análisis y el feedback se deben ejecutar íntegramente en el dispositivo, sin depender de la red durante la sesión | Ejecución manual sin acceso a red. Confirmar que análisis y feedback funcionan. |
| NFR-02 | Rendimiento | El procesamiento por fotograma debe ser compatible con la captura (al menos 15 fps) | Medición del equipo de referencia |
| NFR-03 | Seguridad | Las contraseñas se deben almacenar con hash. | Revisión de código: confirmar el uso de un algoritmo de hash con sal y que la contraseña no se almacena ni se registra en claro en ningún log. |
| NFR-04 | Seguridad | El rol de administración se debe crear exclusivamente mediante un script externo a la UI. | Revisión de código + prueba de intrusión: comprobar que ningún endpoint ni pantalla de la interfaz permite asignar el rol administrador. |
| NFR-05 | Seguridad | Los archivos aportados por el usuario se deben validar por su contenido real y no por su extensión. Las imágenes no deben superar los 10 MB, y los archivos de vídeo, los 200 MB. | Test unitario |
| NFR-06 | Seguridad | Los permisos de cada rol se deben comprobar en la lógica de la aplicación, no solamente ocultando elementos de la interfaz. | Test unitario (uno por combinación rol/acción protegida) |
| NFR-07 | Seguridad | La gestión de cuentas del administrador no debe permitir crear ni promover a nadie al rol administrador | Test unitario |
| NFR-08 | Usabilidad | El feedback sonoro se debe entregar mediante mensajes de voz cortos sin solapamiento | Inspección y pruebas de usuario |
| NFR-09 | Usabilidad | El aviso de modo no personalizado debe ser visible pero no bloquear la práctica. | Inspección y pruebas de usuario |
| NFR-10 | Usabilidad | El MVP debe estar disponible en idioma castellano | Inspección. Textos de interfaz, mensajes de feedback y documentación de usuario están en castellano |
| NFR-11 | Mantenibilidad | La capa de análisis debe estar desacoplada de la interfaz y de la capa de captura | Test automatizado de dependencias entre capas: se verifica que ningún módulo de la capa de análisis importa componentes de la interfaz ni de la capa de captura. |
| NFR-12 | Mantenibilidad | El texto y voz del feedback debe tener una única fuente | Revisión de dependencias |
| NFR-13 | Mantenibilidad | Los umbrales deben vivir fuera del código de forma versionada. | Revisión de dependencias |
| NFR-14 | Mantenibilidad | Los identificadores de código deben estar en idioma inglés | Revisión de código. Inspección de nomenclatura |
| NFR-15 | Portabilidad | El MVP debe soportar Windows y Linux | La suite de pruebas automatizadas se ejecuta con éxito en Windows y Linux mediante integración continua. Lista de comprobación manual en cada sistema para los componentes no automatizables: inicio de la aplicación, calibración completa, sesión con cámara y reproducción de audio. |
| NFR-16 | Portabilidad | La arquitectura debe permitir extraer una API y un cliente móvil futuro | Test automatizado de dependencias entre capas: se verifica que ningún módulo de la capa de análisis importa componentes de la interfaz ni de la capa de persistencia. |
| NFR-17 | Mantenibilidad (Verificabilidad) | El flujo que modela el estado de una calibración debe ser verificado externamente | Test unitario |
| NFR-18 | Mantenibilidad (Verificabilidad) | El flujo que modela la selección de umbrales debe ser verificado externamente | Test unitario |
| NFR-19 | Mantenibilidad (Verificabilidad) | El flujo que modela la autoasignación de atletas debe ser verificado externamente. Dos entrenadores nunca deben poder asignarse a un mismo atleta. | Test unitario |
| NFR-20 | Mantenibilidad (Verificabilidad) | El flujo que modela el proceso de subida de archivos debe ser verificado externamente | Test unitario |
| NFR-21 | Restricción | El sistema debe representar cada desviación postural detectada como un resultado semántico y tipado desacoplado del canal de entrega del feedback | Test automatizado de dependencias por módulo: se verifica que la capa de análisis no importa el motor de feedback ni el reproductor de audio. |
| NFR-22 | Interfaz externa | El sistema debe integrar la librería Mediapipe Tasks (PoseLandmarker) como motor de estimación de pose | Análisis de dependencias por módulo |
| NFR-23 | Rendimiento | El tiempo transcurrido entre la confirmación de un error y el inicio de la reproducción de su locución no debe exceder de 100 ms | Medición instrumentada del intervalo entre la marca de confirmación e inicio de reproducción, sobre al menos 50 eventos. |
| NFR-24 | Rendimiento | La ventana de confirmación aplicada antes de emitir un aviso no debe exceder tres fotogramas con la desviación por encima del umbral, de modo que la corrección se entregue mientras el atleta mantiene la postura que la originó. | Medición instrumentada: número de fotogramas con desviación activa transcurridos entre el que supera el umbral y en que el error se confirma, sobre al menos 50 eventos. Se registra la diferencia temporal, informativamente, al depender de la tasa de captura efectiva. |

---

## 7. Reglas de negocio
directrices, políticas y restricciones lógicas que definen cómo opera el sistema y qué condiciones debe cumplir en sus procesos, independientemente de cómo se implementen.


| ID | Regla de negocio |
|---|---|
| BR-01 | El sistema debe guiar al atleta en el proceso de calibración. |
| BR-02 | Un entrenador solo puede validar calibraciones de atletas que pertenecen a su cartera. |
| BR-03 | Una calibración solo se acepta si cumple los criterios de visibilidad exigidos para cada una de las dos capturas. |
| BR-04 | El sistema únicamente evalúa los errores técnicos observables desde el modo de vista seleccionado; un error no observable desde esa perspectiva no se evalúa durante esa sesión. |
| BR-05 | El modo frontal es válido para cualquier orientación del atleta respecto a la cámara distinta de la lateral; no existe un modo "trasero" independiente. |
| BR-06 | El modo de vista seleccionado rige toda la sesión y no puede cambiarse mientras esta esté en curso. |
| BR-07 | El análisis de un archivo de vídeo no genera una sesión registrada. Sus resultados se muestran al finalizar, pero no se almacenan en el histórico del atleta ni intervienen en el cálculo de sus métricas de progreso. |

---


## 8. Casos de uso
| ID | Caso de uso | Actor | UR de origen | FR | Relación | Alcance |
|---|---|---|---|---|---|---|
| CU-01 | Acceder al sistema (registro e inicio de sesión) | Usuario | UR-01, UR-03 | FR-001, FR-003 | | Soporte |
| CU-02 | Gestionar perfil | Usuario | UR-02, UR-23 | FR-002, FR-030 | | Soporte |
| CU-03 | Gestionar calibración corporal (realizar, consultar estado, recalibrar) | Atleta | UR-04, UR-05, UR-12 | FR-004, FR-005, FR-018 | | Núcleo |
| CU-04 | Practicar sesión de entrenamiento | Atleta | UR-06, UR-07, UR-09, UR-28 | FR-006, FR-007, FR-008, FR-013, FR-014, FR-038, FR-039 | Incluye CU-05 | Núcleo |
| CU-05 | Recibir feedback sonoro en tiempo real | Atleta | UR-08 | FR-009, FR-010, FR-011, FR-012 | Incluido por CU-04 | Núcleo |
| CU-06 | Consultar sesiones y progreso | Atleta, Entrenador | UR-10, UR-11, UR-19, UR-20 | FR-015, FR-016, FR-017, FR-026, FR-027 | Extendido por CU-09 | Núcleo |
| CU-07 | Validar calibración de un atleta | Entrenador | UR-16, UR-18 | FR-023, FR-025, FR-034 | | Núcleo |
| CU-08 | Asignar ejercicios correctivos | Entrenador | UR-22 | FR-029, FR-035 | | Visión ampliada |
| CU-09 | Seguir realización ejercicios correctivos | Atleta, Entrenador | UR-13 | FR-019, FR-020 | Extiende CU-06 | Visión ampliada |
| CU-10 | Gestionar banco de ejercicios correctivos | Entrenador, Administrador | UR-21, UR-27 | FR-028, FR-037 | | Visión ampliada |
| CU-11 | Gestionar relación Atleta – Entrenador | Usuario | UR-14, UR-15, UR-17, UR-25 | FR-021, FR-022, FR-024, FR-033 | | Visión ampliada |
| CU-12 | Gestionar cuentas y auditar actividad | Administrador | UR-24, UR-26 | FR-031, FR-032, FR-036 | | Visión ampliada |


## 9. Trazabilidad con los marcos de referencia

### 9.1 Dimensiones del marco CARAIX

| Dimensión | Requisitos derivados |
|---|---|
| Colaboración | UR-13, UR-16, UR-18; FR-019, FR-020, FR-023, FR-025; BR-02 |
| Adaptabilidad | UR-04, UR-06, UR-07, UR-09; FR-004, FR-006, FR-007, FR-008, FR-013; BR-04 |
| Responsabilidad | UR-26; FR-007, FR-011, FR-034, FR-035, FR-036; NFR-03, NFR-04, NFR-06; BR-02, BR-07 |
| Explicabilidad | UR-10, UR-11, UR-19, UR-20; FR-010, FR-015, FR-016, FR-017, FR-026, FR-027, FR-038, FR-039; NFR-21 |

### 9.2 Fases del modelo SMDD

| Fase | Requisitos |
|---|---|
| Sensing | FR-013, FR-014, FR-038; NFR-02, NFR-22; BR-03 |
| Modeling | FR-004, FR-005, FR-008, FR-018; NFR-13, NFR-17, NFR-18 |
| Design | FR-009, FR-012, FR-015; NFR-21; BR-04, BR-05 |
| Delivery | FR-006, FR-007, FR-010, FR-011, FR-016, FR-017; NFR-08, NFR-09 |

---