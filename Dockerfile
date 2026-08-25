FROM python:3.14-slim

WORKDIR /app

# dependências primeiro: só reinstala quando requirements.txt muda
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dados/ dados/
COPY nivel_1/ nivel_1/
COPY nivel_2/ nivel_2/
COPY docs/ docs/
COPY README.md ENTREGA.yaml ./

# outputs/ é montado como volume no runtime, para os resultados saírem do container
RUN mkdir -p outputs

# A chave NUNCA entra na imagem: vem por variável de ambiente no docker run.
# O .dockerignore garante que um .env local não seja copiado por acidente.
WORKDIR /app/nivel_2
CMD ["python", "agente.py"]
