
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    HK_CONNECTIVITY_NODE as unique_field,
    count(*) as n_records

from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`hub_connectivity_node`
where HK_CONNECTIVITY_NODE is not null
group by HK_CONNECTIVITY_NODE
having count(*) > 1



  
  
      
    ) dbt_internal_test