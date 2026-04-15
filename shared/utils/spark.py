import sys
from typing import Optional, cast

from shared.logger.default_logger import default_logger

SparkSessionType = None

try:
    from pyspark.sql import SparkSession

    SparkSessionType = SparkSession
except ImportError:
    pass  # PySpark not available (e.g., during Sphinx doc build)


def get_spark() -> Optional[SparkSession]:
    if "sphinx" not in sys.modules:
        from pyspark.sql import SparkSession

        return SparkSession.builder.getOrCreate()

    else:
        return None


def get_dbutils(spark):  # type: ignore
    try:
        from pyspark.dbutils import DBUtils

        return DBUtils(spark)  # type: ignore
    except:
        default_logger.error("Dbutils not available")


# Initialize Spark session
# To work with shared cluster with streaming

# spark = get_spark()  # type: ignore

spark = cast(SparkSession, get_spark())  # type: ignore
dbutils = get_dbutils(spark)  # type: ignore
