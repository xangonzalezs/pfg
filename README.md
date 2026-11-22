# Diseño, implementación y evaluación de un sistema de visión artificial con feedback auditivo para la mejora de la técnica en ejercicios posturales

[![Pruebas](https://github.com/xangonzalezs/pfg/actions/workflows/pruebas.yml/badge.svg)](https://github.com/xangonzalezs/pfg/actions/workflows/pruebas.yml)

Sistema de visión artificial con feedback auditivo en tiempo real para la
mejora de la técnica en la ejecución del pino (*handstand*).

Proyecto de Fin de Grado en Ingeniería Informática, UNED.
Autor: Xan González Salgado.

## Design, Implementation and Evaluation of a Computer Vision System with Auditory Feedback for Improving Technique in Postural Exercises
A computer vision system providing real-time auditory feedback to improve technique in the execution of the handstand.

Final Degree Project in Computer Engineering, UNED.
Author: Xan González Salgado


## Requisitos   (requirements)

- Python 3.10 o 3.11
- Una cámara web
- Altavoces o auriculares
- En Linux, el paquete del sistema que proporciona Tk (ver más abajo). No se instala con pip.

## Instalación  (installation)

1. Tk, solo en Linux
La interfaz usa Tk, que no se distribuye en PyPI. En Windows ya viene incluido.
```
sudo apt install python3-tk      # Ubuntu y derivadas
```


2. Clonar el repositorio 

```
git clone https://github.com/xangonzalez/pfg
cd pfg
```

3. Crear un entorno virtual
```
# Windows
python -m venv .venv

# Linux
python3 -m venv .venv
```

4. Activar el entorno

```
# Windows
.venv\Scripts\activate

# Linux
source .venv/bin/activate
```

5. Instalar las dependencias:

```
pip install -r requirements.txt
```

6. Modelo de estimación de pose
El modelo de MediaPipe no se versiona por su tamaño, de modo que hay que descargarlo antes del primer arranque
```
python scripts/download_model.py
```

7. Primera cuenta de entrenador
Las cuentas de atleta se crean desde el registro de la propia aplicación. Las de entrenador y administrador, no. Se crean con un script externo a la interfaz, que para el rol de administración es además un requisito del sistema.
```
python scripts/create_account.py trainer entrenador1 "Nombre Apellido"
```
8. Asignar atletas a entrenadores
En el MVP la cartera de un entrenador se compone desde fuera de la interfaz, igual que las cuentas de entrenador y de administrador. El atleta se registra solo desde la aplicación y queda sin entrenador asignado hasta que se ejecuta:
```
python scripts/assign_trainer.py <atleta> <entrenador>
```

Para retirarlo de la cartera en la que esté:
```
python scripts/assign_trainer.py <atleta> --ninguno
```

## Ejecución de los tests   (running the tests)

Desde la raíz del proyecto:

```
pytest
```

## Estructura del proyecto  (project structure)

```text
├── main.py               # Punto de entrada de la aplicación
├── requirements.txt      # Dependencias
├── pytest.ini            # Configuración de las pruebas
├── setup.cfg             # Configuración del análisis de mutación
├── core/                 # Lógica del sistema, independiente de la interfaz
│   ├── models/           # Estructuras de datos compartidas entre capas
│   ├── vision/           # Captura de fotogramas y estimación de pose
│   ├── analysis/         # Análisis geométrico de la postura y detección de errores
│   ├── calibration/      # Medición de la postura neutra del atleta
│   ├── config/           # Carga de umbrales y derivación de los personalizados
│   ├── feedback/         # Catálogo de mensajes, reproducción y selección de avisos
│   ├── persistence/      # Esquema de la base de datos y acceso a los datos
│   └── services/         # Coordinación de sesión, calibración, cuentas y permisos
├── ui/                   # Interfaz de escritorio: ventana, estado y render
│   ├── views/            # Una clase por pantalla de la aplicación
├── assets/
│   ├── config/           # Umbrales genéricos (umbrales.json)
│   ├── messages/         # Catálogo de textos del feedback
│   ├── audio/            # Locuciones sintetizadas
│   └── models/           # Modelo de MediaPipe (no versionado)
├── scripts/              # Preparación del entorno, externos a la interfaz
├── tests/                # Pruebas unitarias
├── diagramas/            # Diagramas UML de la memoria
└── docs/                 # Especificación de requisitos
```