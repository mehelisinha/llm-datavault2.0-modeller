
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select HASHDIFF_CONNECTIVITY_NODE_DETAILS
from `edh_unreg_silver_dev_st`.`raw_staging`.`stg_connectivity_nodes`
where HASHDIFF_CONNECTIVITY_NODE_DETAILS is null



  
  
      
    ) dbt_internal_test