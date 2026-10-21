#!/bin/bash
set -euo pipefail

if [[ "$#" -ne 3 ]]; then
    echo "Usage: $0 BOOK_URL BUCKET EXPIRATION_SECONDS" >&2
    exit 1
fi

BOOK_URL="$1"
BUCKET="$2"
EXPIRES="$3"

if ! [[ "$EXPIRES" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: expiration must be a positive integer." >&2
    exit 1
fi

FILENAME="${BOOK_URL##*/}"

if [[ -z "$FILENAME" ]]; then
    echo "Error: could not determine filename from URL." >&2
    exit 1
fi

mkdir -p books
echo "Downloading $FILENAME..."
curl --fail --location --silent --show-error --retry 2 "$BOOK_URL" --output "books/$FILENAME"

if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket already exists and is accessible: $BUCKET"
else
    echo "Creating private bucket: $BUCKET"
    aws s3 mb "s3://$BUCKET" --region us-east-1
fi

aws s3 cp "books/$FILENAME" "s3://$BUCKET/$FILENAME" --content-type "text/plain; charset=utf-8"

PRESIGNED_URL="$(aws s3 presign "s3://$BUCKET/$FILENAME" --expires-in "$EXPIRES" --region us-east-1)"

echo "Presigned URL (expires after $EXPIRES seconds):"
echo "$PRESIGNED_URL"
