# Similar Products API

API REST que devuelve el detalle de los productos similares a uno dado, orquestando dos APIs existentes (`similarids` y `product`).

- Enunciado original: [docs/original-statement.md](docs/original-statement.md)
- Contrato expuesto: [similarProducts.yaml](similarProducts.yaml)
- APIs consumidas: [existingApis.yaml](existingApis.yaml)

> Trabajo en curso. Este README se completa en cada hito con instrucciones de ejecución y decisiones técnicas.

## Plan

1. Dominio y caso de uso con tests unitarios (sin red).
2. Adaptador HTTP de salida hacia las APIs existentes.
3. Adaptador HTTP de entrada (FastAPI) en el puerto 5000.
4. Resiliencia y rendimiento: timeouts, fallos parciales, caché y circuit breaker.
5. Docker, test de rendimiento con k6 y documentación final.
