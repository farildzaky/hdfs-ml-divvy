#!/bin/sh
# Empties the app: HDFS data (including the model copy) and results.
# The source CSV files and the trained model in model/ are kept.
set -eu
cd "$(dirname "$0")/.."

if curl -s localhost:8000/api/jobs | grep -q '"status":"\(queued\|running\)"'; then
  echo "Masih ada import yang berjalan. Tunggu sampai selesai, lalu ulangi."
  exit 1
fi

echo "Ini menghapus permanen /bikeshare di HDFS, data/results, dan data/uploads."
echo "File CSV sumber dan model di folder model/ tidak dihapus."
printf "Ketik HAPUS untuk lanjut: "
read -r answer
[ "$answer" = "HAPUS" ] || { echo "Dibatalkan."; exit 1; }

docker compose stop backend
docker compose exec -T namenode hdfs dfs -rm -r -f -skipTrash /bikeshare
rm -rf data/results data/uploads
docker compose start backend
echo "Selesai. Data sudah kosong, silakan import dari website."
