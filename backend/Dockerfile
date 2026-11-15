# Backend = SAME Spark image as the worker (identical Spark & Python)
# plus FastAPI + preprocessing deps. Acts as the Spark driver (client mode).
FROM apache/spark:3.5.3

USER root
WORKDIR /opt/app

# Perintah di README memakai `python -m app.cli`, sedangkan image Spark hanya punya `python3`.
RUN ln -sf /usr/bin/python3 /usr/local/bin/python

# Hadoop client jars for hdfs:// access are already on the Spark image.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Expose the Spark image's bundled pyspark/py4j to plain `python`/uvicorn.
ENV PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip:/opt/app \
    PYTHONUNBUFFERED=1 \
    PYSPARK_PYTHON=python3 \
    SPARK_MASTER=spark://spark-master:7077 \
    HDFS_NAMENODE=hdfs://namenode:9000 \
    WEBHDFS_URL=http://namenode:9870/webhdfs/v1 \
    DATA_RAW=/opt/app/data/raw

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
