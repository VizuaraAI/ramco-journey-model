FROM python:3.11-slim
WORKDIR /app

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code + the deterministic model files
COPY chatbot/      /app/chatbot/
COPY out/          /app/out/
COPY eval/         /app/eval/

# HF Spaces injects PORT — Flask must bind to it
ENV PORT=7860
EXPOSE 7860

# Drop into the webapp dir so relative paths resolve
CMD ["python", "chatbot/webapp/app.py"]
