
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select HASHDIFF_CE_DETAILS
from `edh_unreg_silver_dev_st`.`raw_staging`.`stg_conducting_equipment`
where HASHDIFF_CE_DETAILS is null



  
  
      
    ) dbt_internal_test