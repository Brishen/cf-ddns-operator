FROM ubuntu:latest
LABEL authors="bhawkins"

ENTRYPOINT ["top", "-b"]