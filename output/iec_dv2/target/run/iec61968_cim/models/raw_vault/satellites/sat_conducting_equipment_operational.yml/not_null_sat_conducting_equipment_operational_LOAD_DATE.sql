
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select LOAD_DATE
from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`sat_conducting_equipment_operational`
where LOAD_DATE is null



  
  
      
    ) dbt_internal_test