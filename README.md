# JAQUIS Repostería Gourmet

MVP funcional para toma de pedidos web, envío a WhatsApp, pantalla operativa tipo cocina y reportes.

## Ejecutar localmente

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Abrir `http://127.0.0.1:8000`

## Estructura
- `/templates`: vistas HTML
- `/static`: estilos y archivos cargados
- `app.py`: aplicación FastAPI
- `jaquis.db`: base de datos SQLite local

## GitHub
Yo no puedo hacer push directo a su repositorio desde aquí. Para subirlo a `https://github.com/jSERRANO007/Jaquis_Reposteria` use:

```bash
git init
git branch -M main
git remote add origin https://github.com/jSERRANO007/Jaquis_Reposteria.git
git add .
git commit -m "feat: MVP inicial JAQUIS Repostería Gourmet"
git push -u origin main
```
