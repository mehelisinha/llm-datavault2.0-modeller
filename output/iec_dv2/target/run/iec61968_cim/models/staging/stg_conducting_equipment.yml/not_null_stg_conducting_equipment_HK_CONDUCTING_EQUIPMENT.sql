
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select HK_CONDUCTING_EQUIPMENT
from `edh_unreg_silver_dev_st`.`raw_staging`.`stg_conducting_equipment`
where HK_CONDUCTING_EQUIPMENT is null



  
  
      
    ) dbt_internal_test