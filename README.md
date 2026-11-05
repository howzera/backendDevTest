# Similar Products API

API REST que devuelve el detalle de los productos similares a uno dado, orquestando dos APIs existentes (`similarids` y `product`).

- Enunciado original: [docs/original-statement.md](docs/original-statement.md)
- Contrato expuesto: [similarProducts.yaml](similarProducts.yaml)
- APIs consumidas: [existingApis.yaml](existingApis.yaml)

```
GET /product/{productId}/similar
200 -> [{"id": "2", "name": "Dress", "price": 19.99, "availability": true}, ...]   (orden de similitud)
404 -> {"detail": "Product '999' not found"}
503 -> {"detail": "Similar products for '1' are temporarily unavailable"}
```

## Ejecución

Requisitos: Docker. En Windows/macOS puede ser necesario compartir la carpeta `shared` en Docker Desktop.

```bash
# 1. Mocks, InfluxDB, Grafana y la aplicación (puerto 5000)
docker-compose up -d simulado influxdb grafana
docker-compose up -d --build app

# 2. Comprobación rápida
curl http://localhost:5000/product/1/similar

# 3. Test de rendimiento
docker-compose run --rm k6 run scripts/test.js
# Resultados: http://localhost:3000/d/Le2Ku9NMk/k6-performance-test
```

Sin Docker (Python 3.12):

```bash
python -m venv .venv && .venv/Scripts/activate    # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 5000   # usa http://localhost:3001 por defecto
pytest                                             # 35 tests
```

Swagger de la API: http://localhost:5000/docs

## Arquitectura hexagonal

```
app/
├── domain/                     # Núcleo: Python puro, sin FastAPI ni httpx
│   ├── models.py               #   ProductDetail (value object inmutable)
│   ├── exceptions.py           #   ProductNotFoundError / ProductUnavailableError
│   └── ports.py                #   ProductRepository (puerto de salida)
├── application/
│   └── get_similar_products.py # Caso de uso: orquestación y reglas de negocio
├── infrastructure/
│   ├── http_api/               # Adaptador de ENTRADA (FastAPI): HTTP <-> dominio, errores -> 404/503
│   └── product_client/         # Adaptadores de SALIDA, todos implementan ProductRepository
│       ├── http_product_repository.py    # cliente httpx de las APIs existentes
│       ├── circuit_breaker.py            # decorador: circuit breaker por recurso
│       └── cached_product_repository.py  # decorador: caché TTL + single-flight
├── config.py                   # Configuración por variables de entorno
└── main.py                     # Composition root: el único sitio que conoce todas las piezas
```

Las dependencias apuntan hacia dentro: el dominio no importa nada de infraestructura. El caso de uso recibe el puerto por constructor, así que se testea con un repositorio falso, sin red.

La resiliencia y el caché son **decoradores del mismo puerto**, montados en `main.py`:

```
GetSimilarProducts -> CachedProductRepository -> CircuitBreakerProductRepository -> HttpProductRepository -> mocks
```

Se pueden añadir, quitar o reordenar sin tocar el caso de uso (principio abierto/cerrado).

## Decisiones técnicas

**Python + FastAPI en lugar de Java + Spring WebFlux.** El enunciado recomienda Spring, pero permite cualquier lenguaje. Elegí el stack que domino para poder justificar cada línea. FastAPI con `asyncio` es no bloqueante, como WebFlux: una llamada lenta no ocupa un hilo. Equivalencias: `WebClient` -> `httpx.AsyncClient`, `flatMapSequential` -> `asyncio.gather`, `.timeout()` -> `asyncio.wait_for`, Resilience4j -> circuit breaker propio (60 líneas, testeado).

**Respuesta parcial ante fallos.** Si un similar no existe (404), falla (500) o tarda más de `DETAIL_TIMEOUT_SECONDS` (1,5 s), se omite y se devuelven los demás. Para el negocio es mejor mostrar 2 recomendaciones que ninguna. El orden de similitud se conserva porque `asyncio.gather` devuelve en el orden de entrada, no de llegada.

**404 vs 503.** 404 solo si el producto pedido no existe (`similarids` responde 404). Si `similarids` falla o no responde, devuelvo 503 con cuerpo JSON: devolver `[]` ocultaría el fallo y el frontend lo trataría como "sin similares". El 503 no está en el contrato; es la respuesta REST estándar para una dependencia caída.

**Timeouts en dos niveles.**
- `DETAIL_TIMEOUT_SECONDS=1.5`: lo máximo que una petición espera por un similar.
- `UPSTREAM_TIMEOUT_SECONDS=10`: límite duro de cualquier llamada HTTP, para no acumular conexiones colgadas.

**Caché en memoria con TTL y single-flight.** Los datos no cambian en cada petición, así que se cachean `similarids` y los detalles (TTL 300 s) y también los "no encontrado" (TTL 60 s). Los errores **no** se cachean.
- *Single-flight*: si 200 usuarios piden el producto 1 a la vez, sale **una** llamada al mock y todos esperan la misma.
- *Late completion*: la llamada compartida está protegida con `asyncio.shield`. Si una petición se rinde por timeout, la llamada sigue y su resultado entra en caché. Por eso el producto 1000 (5 s) se omite la primera vez pero aparece en las siguientes, en 3 ms.

**Circuit breaker por recurso.** Tras 5 fallos seguidos de un recurso (p. ej. `product:6`), el circuito se abre 10 s y se falla al instante, sin cargar un servicio que ya está mal. Luego deja pasar una única llamada de prueba. Es por recurso y no global: un producto roto no debe cortar los sanos. Un 404 es una respuesta válida y no cuenta como fallo.

**Un solo worker de uvicorn.** El caché y los circuit breakers viven en memoria del proceso. Con varios workers cada uno tendría su copia. En producción usaría un caché compartido (Redis).

## Resultados de rendimiento (k6)

`docker-compose run --rm k6 run scripts/test.js`, 200 usuarios por escenario, aplicación en Docker sobre Windows 11 (Docker Desktop):

| Métrica | Sin caché (commit `3b02d1c`) | Versión final | Mejora |
|---|---|---|---|
| Duración media | 4,43 s | **161 ms** | ×27 |
| Mediana | 3,79 s | **3,2 ms** | ×1.000 |
| p95 | 9,71 s | **1,50 s** | ×6 |
| Máximo | 15,7 s | **1,56 s** | ×10 |
| Throughput | 30 req/s | **256 req/s** | ×8 |

Latencia por escenario con la caché caliente:

| Escenario k6 | Petición | Respuesta | Tiempo |
|---|---|---|---|
| normal | `/product/1/similar` | 2, 3, 4 | 3 ms |
| notFound | `/product/4/similar` | 1, 2 (5 no existe: se omite) | 3 ms |
| error | `/product/5/similar` | 1, 2 (6 da 500: se omite) | 6 ms |
| slow | `/product/2/similar` | 3, 100, 1000 (1000 llegó tarde y quedó en caché) | 3 ms |
| verySlow | `/product/3/similar` | 100, 1000 (10000 tarda 50 s: se omite) | 1,5 s |

El p95 de 1,5 s es el escenario `verySlow`: el producto 10000 supera el límite duro de 10 s, nunca entra en caché y cada petición espera el timeout de 1,5 s. Es un compromiso consciente: bajar el timeout reduciría la latencia, pero dejaría fuera productos lentos pero válidos como el 100 (1 s).

## Tests

```bash
pytest   # 35 tests, < 2 s, sin red ni Docker
```

| Fichero | Qué cubre |
|---|---|
| `tests/unit/test_get_similar_products.py` | Orden de similitud, lista vacía, 404, fallo de `similarids`, similar inexistente / con error / lento (un test por escenario de k6), concurrencia |
| `tests/unit/test_cached_product_repository.py` | Acierto de caché, single-flight (200 llamadas -> 1), expiración por TTL, caché de "no encontrado", no cachear errores, late completion |
| `tests/unit/test_circuit_breaker.py` | Apertura tras N fallos, half-open con una sola prueba, cierre/reapertura, aislamiento por recurso, 404 no es fallo |
| `tests/integration/test_http_product_repository.py` | Respuestas reales del mock: ids numéricos -> string, 404 en texto plano y en JSON, 500 con cuerpo vacío, JSON inválido, timeout, error de conexión |
| `tests/integration/test_api.py` | Forma del contrato, respuesta parcial, 404 y 503 con cuerpo de error |

El tiempo se inyecta (`clock`) para testear TTL y circuit breaker sin `sleep`.

## Qué cambiaría en producción

- **Caché compartida (Redis)** para escalar a varias réplicas, y caché con tamaño máximo (LRU) además de TTL.
- **Observabilidad**: métricas (aciertos de caché, estado de circuitos, latencia por dependencia) con Prometheus/OpenTelemetry y logs estructurados.
- **Stale-while-revalidate**: servir el dato expirado mientras se refresca en segundo plano.
- **Fallar rápido con productos conocidos como lentos** (p. ej. el 10000) en lugar de esperar el timeout en cada petición.
- **Health checks** (`/health`) y límites de concurrencia por dependencia (bulkhead).
