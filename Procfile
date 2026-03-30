web: gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 2 --timeout 120 --bind 0.0.0.0:$PORT --log-level info
