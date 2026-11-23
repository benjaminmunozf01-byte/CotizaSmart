# CotizaSmart — Cotizador de Obras con Riesgo Medido (Montecarlo)

**Trabajo 3 · Tecnología de la Información II**  
**Carrera:** Ingeniería Comercial — Universidad de Concepción, Campus Los Ángeles  
**Autores:** Jorge Campos, Benjamin Muñoz y Raul Vergara

---

## 1. Descripción del Producto

**CotizaSmart** es una plataforma SaaS B2B para contratistas pequeños y medianos de Chile (primer rubro: **instalaciones eléctricas**). Resuelve el problema de cotizar con planillas desactualizadas que olvidan mermas, subestiman horas-hombre y no miden el riesgo de sobrecosto.

- **Simulación Montecarlo PERT (10.000 escenarios):** muestreo vectorizado en `NumPy` (< 0,1 segundos) a partir de rangos *mínimo, probable y máximo* por partida.
- **Sensibilidad Macroeconómica Correlacionada:** sliders de variación del precio del **Cobre (-20% a +30%)** y del **Dólar (-10% a +15%)** con correlación entre partidas sensibles al cobre (método Iman-Conover).
- **Curva de Precio Óptimo:** cruza la probabilidad de ganar la licitación $P(\text{win}\mid\text{precio})$ con el margen esperado para recomendar el precio que **maximiza la ganancia esperada** y reduce la probabilidad de pérdida a zona verde ($\le 10\%$).
- **Calibración con CSV:** soporta distribución empírica con precios adjudicados de la competencia (`precios_competencia_ejemplo.csv`) y regresión logística sobre historial propio (`historial_cotizaciones_ejemplo.csv`).
- **Propuesta Comercial en PDF:** genera un documento ejecutivo en CLP + IVA (19%) con ReportLab sin exponer márgenes internos, mermas ni rangos de incertidumbre al cliente.

---

## 2. Ejecución Local (Comando Único y Respaldo para Pitch)

### Requisitos previos
- Python 3.11 o superior.

### Instalación y arranque rápido
```bash
cd CotizaSmart
pip install -r requirements.txt
python app.py
```

Luego abre en el navegador:  
👉 **`http://127.0.0.1:5000`**

> **Nota sobre los datos iniciales (Seed):** Al iniciar por primera vez, CotizaSmart crea automáticamente la base SQLite (`cotizasmart.db`), genera los 3 archivos CSV de ejemplo en `data/` y precarga 10 cotizaciones con fechas dinámicas relativas al día actual de modo que el contador del Plan Gratuito muestre siempre **`"2 de 3 cotizaciones usadas este mes"`**. En la barra lateral inferior dispones además del botón **"Restablecer datos de demostración"** para volver a este estado inicial en cualquier momento.

### Ejecutar pruebas automatizadas (`pytest`)
```bash
cd CotizaSmart
pytest -v
```

---

## 3. Despliegue en Render o Railway (URL Pública)

El proyecto incluye `requirements.txt`, `runtime.txt`, `Procfile` y `render.yaml` listos para producción con `gunicorn`.

### Pasos para desplegar en Render (Web Service Gratuito)
1. Sube la carpeta `CotizaSmart` a un repositorio en GitHub.
2. Ingresa a [https://render.com](https://render.com) y selecciona **New +** &rarr; **Web Service**.
3. Conecta tu repositorio de GitHub (`benjaminmunozf01-byte/CotizaSmart`):
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
4. Selecciona el plan **Free** y haz clic en **Create Web Service**. En ~2 minutos obtendrás tu URL pública (`https://cotizasmart-xxxx.onrender.com`).

> ⚠️ **ADVERTENCIA IMPORTANTE SOBRE RENDER GRATIS PARA LA DEMO EN VIVO:**
> 1. **Modo reposo (Cold Start):** En el plan gratuito de Render, el servidor se duerme tras 15 minutos de inactividad y tarda ~40–50 segundos en despertar en la primera visita. **Abre la URL pública 3 minutos antes de comenzar el pitch.**
> 2. **Almacenamiento efímero:** En Render Free el disco local no persiste entre reinicios del contenedor; cuando el servicio se reinicia, vuelve automáticamente a los datos de demostración iniciales (*seed* con `"2 de 3 cotizaciones usadas este mes"`), lo cual es ideal para demostraciones repetibles.
> 3. **Respaldo local infalible para el pitch:** Mantén una terminal abierta con la app corriendo localmente (`cd CotizaSmart && python app.py` en `http://127.0.0.1:5000`) por si la conexión Wi-Fi de la sala falla durante la presentación.

---

## 4. Guion Cronometrado de Demo en Vivo (90 Segundos)

Este guion está diseñado para ejecutarse dentro del pitch de 5 minutos ante el inversionista:

- **0:00 – 0:15 | 1. Panel y Problema (Pantalla 1: Panel de Inicio)**
  - Muestra los KPIs del mes, la insignia **"Datos de demostración"** y el contador del Plan Gratuito (**"2 de 3 cotizaciones usadas este mes"**).
  - Haz clic en **"Ver Cotización Demo (120 m² Los Ángeles)"** para abrir el caso estrella: *"Instalación eléctrica local comercial 120 m² - Los Ángeles"*.

- **0:15 – 0:40 | 2. Precio Ingenuo vs. Precio Óptimo y Diagnóstico de Tornado (Pantalla 3: Resultados)**
  - Señala el contraste en el **Semáforo Grande**:
    - Si el contratista cobra el tradicional **Costo + 20%** (`$12.644.705`), queda en **Semáforo Amarillo con `12,5%` de probabilidad de perder plata** (`87,5%` de ganar dinero), porque las desviaciones de obra e imprevistos tienen una cola alcista que el recargo plano de 20% no alcanza a cubrir con seguridad.
    - **El beneficio clave del Precio Óptimo recomendado por CotizaSmart (`$13.314.270`, `+26,4%` sobre el costo esperado de `$10.537.254`) es bajar la probabilidad de pérdida de `12,5%` (Amarillo) a solo `7,5%` (Semáforo Verde, `92,5%` de probabilidad de ganar dinero)**, al mismo tiempo que incrementa la ganancia esperada total de `$1.241.374` a `$1.320.867`.
  - Muestra el **Diagrama de Tornado** abajo con los valores reales del caso: evidencia ante el inversionista que **los imprevistos técnicos de obra (`22,5%` del riesgo, $\pm\$407.476$) y la mano de obra (`Maestro electricista primera` con `20,9%` y `Ayudante eléctrico avanzado` con `14,6%`) explican en conjunto el `58,0%` de la incertidumbre total del proyecto**, por encima de las luminarias LED importadas (`6,6%`), la canalización EMT (`5,7%`) y los conductores de cobre THHN (`3,0%`).

- **0:40 – 0:60 | 3. Shock Independiente Cobre/Dólar y Calibración con CSV de Competencia Normalizado por $\text{m}^2$**
  - En la barra *"Simulador de Estrés en Vivo"*, mueve los sliders de **Cobre (+15%)** (que afecta a los cables THHN, malla a tierra, tableros y protecciones) y **Dólar (+8%)** (que afecta independientemente solo a las partidas marcadas como sensibles al dólar: luminarias LED, tableros y protecciones importadas).
  - Carga `data/precios_competencia_ejemplo.csv` (40 licitaciones adjudicadas con columna `superficie_m2`): CotizaSmart normaliza automáticamente los precios de competencia a $\text{CLP/m}^2$ para compararlos de forma justa contra los $120\text{ m}^2$ del local comercial.

- **0:60 – 0:75 | 4. Slider de Precio en Tiempo Real**
  - Arrastra el **Slider de Precio Ofertado** bajo la Curva de Precio Óptimo (o presiona *"Probar Ingenuo Costo + 20%"* y luego *"Usar Precio Óptimo"*): muestra cómo cambian instantáneamente la línea en el histograma, la probabilidad de ganar, el riesgo de pérdida y el color del semáforo. Haz clic en **"Guardar cotización"**.

- **0:75 – 0:90 | 5. Propuesta Comercial en PDF y Cierre de Negocio**
  - Haz clic en **"Generar propuesta PDF"**: muestra la vista previa para el cliente (sin márgenes internos ni rangos, con Subtotal Neto, IVA 19% y Total CLP) y descarga el archivo PDF profesional en vivo.
  - Cierra mostrando las pestañas **Planes** (`$49.000 CLP/mes`) y **Hoja de Ruta** (dejando claro que la Fase 2 con Mercado Público y la Fase 3 regional son las etapas post-inversión).
