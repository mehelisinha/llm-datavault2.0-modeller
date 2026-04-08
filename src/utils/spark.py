from pyspark.sql import SparkSession


def get_spark() -> SparkSession:
    spark = SparkSession.getActiveSession()
    if spark is None:
        spark = SparkSession.builder.getOrCreate()
    return spark


def get_dbutils(spark):  # type: ignore

    from pyspark.dbutils import DBUtils

    return DBUtils(spark)  # type: ignore


# Initialize Spark session
# To work with shared cluster with streaming

# spark = get_spark()  # type: ignore

spark = get_spark()
dbutils = get_dbutils(spark)  # type: ignore
