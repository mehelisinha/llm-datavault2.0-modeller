// Workspace definition for the DWA architecture model
workspace "DWA Architecture" "C4 model for the Data Warehouse Automation project" {
    !docs architecture.md

    // Model section defines actors, systems, containers, and components
    model {
        // Actors: human users and data engineers
        dataEngineer = person "Data Engineer" "Defines metadata, reviews models and monitors execution"
        // user = person "User" "Uses the data warehouse for analytics and reporting"

        // External systems used by DWA
        sourceSystems = softwareSystem "Source Systems" "EDH Core data systems feeding the warehouse"
        databricks = softwareSystem "Databricks Platform" "Cloud data platform hosting Delta Lake and DBT execution"
        edhDatabase = softwareSystem "Enterprise Data Hub" "Centralized data repository for raw and curated data"

        // DWA software system with internal containers and components
        dwa = softwareSystem "Data Warehouse Automation" "Generates and executes DBT-based Data Vault pipelines from metadata" {
            //=========================CONTAINER Metadata Store ===========================================
            // Metadata Store container holds structured configuration for the DBT pipeline
            metadataStore = container "Metadata Store" "Stores system, table, staging and vault metadata as CSV, Delta tables, or other config sources" {
                systemsConfig = component "Systems Configuration" "Defines source system metadata and source types"
                tablesConfig = component "Source Table Configuration" "Defines source tables, schemas, and relationships"

                stagingConfig = component "Staging Configuration" "Defines staging models, materialization, filters, and derived columns"
                rawVaultConfig = component "Raw Vault Configuration" "Defines hub, link, and satellite metadata for the Raw Vault"
                martsConfig = component "Mart Configuration" "Defines dimension and fact table specifications and aggregations"
                testsConfig = component "Test Configuration" "Defines data quality and dbt test specifications"

                systemsConfig -> tablesConfig "Defines source table metadata"
                tablesConfig -> stagingConfig "Defines staging model metadata"
                stagingConfig -> rawVaultConfig "Feeds raw vault metadata"
                rawVaultConfig -> martsConfig "Feeds mart and dimensional model definitions"
                martsConfig -> testsConfig "Feeds test definitions"
            }

            // Core DWA containers: scheduler, builder, and runner

            //=========================CONTAINER DataVault Builder ===========================================

            projectBuilder = container "DataVault Builder" "Generates DBT project files, models, macros, and YAML metadata from input metadata" {
                metadataReader = component "Metadata Reader" "Loads and parses metadata from CSV or Delta sources"
                validator = component "Validator" "Validates metadata schema and cross-references"
                parser = component "Parser" "Extracts system and model specifications from metadata"
                hubGenerator = component "Hub Generator" "Creates hub SQL and metadata files"
                linkGenerator = component "Link Generator" "Creates link SQL and relationship definitions"
                satelliteGenerator = component "Satellite Generator" "Creates satellite SQL and SCD type 2 support"
                macroGenerator = component "Macro Generator" "Generates dbt macros for hashing, keys, and transformations"
                testGenerator = component "Test Generator" "Generates dbt tests and test configuration files"
                configGenerator = component "Config Generator" "Generates dbt_project.yml, sources.yml, and config files"
                fileWriter = component "File Writer" "Writes generated dbt files to the Databricks workspace"

                metadataReader -> validator "Validates metadata"
                validator -> parser "Parses validated metadata"
                parser -> hubGenerator "Generates hub definitions"
                parser -> linkGenerator "Generates link definitions"
                parser -> satelliteGenerator "Generates satellite definitions"
                parser -> macroGenerator "Generates macros"
                parser -> testGenerator "Generates tests"
                parser -> configGenerator "Generates config files"
                hubGenerator -> fileWriter "Writes hub files"
                linkGenerator -> fileWriter "Writes link files"
                satelliteGenerator -> fileWriter "Writes satellite files"
                macroGenerator -> fileWriter "Writes macro files"
                testGenerator -> fileWriter "Writes test files"
                configGenerator -> fileWriter "Writes config files"
            }

            //=========================CONTAINER DataVault Runner ===========================================

            projectRunner = container "DataVault Runner" "Runs DBT models, captures audit logs, and persists outputs" {
                scheduler = component "Scheduler" "Time-based or event-based orchestration for DBT runs and metadata refresh"
                dbtEngine = component "DBT Engine" "Compiles and executes DBT models"
                rawVault = component "Raw Vault / Delta Lake" "Represents hub, link, and satellite storage within the execution pipeline"
                pitLayer = component "PIT Layer" "Represents point-in-time tables for reporting and dimensional load"
                starSchema = component "Star Schema Layer" "Represents dimensional models for analytics"
                auditLog = component "Audit & Lineage Store" "Captures execution logs, version history, and lineage metadata"

                scheduler -> dbtEngine "Triggers"
                dbtEngine -> rawVault "Loads hub/link/satellite tables"
                rawVault -> pitLayer "Feeds point-in-time generation"
                pitLayer -> starSchema "Feeds dimensional models"
                dbtEngine -> auditLog "Writes execution logs"
            }

            //=========================CONTAINER DataVault Lineage ===========================================
            entityRelationship = container "Entity Relationship" "Runs DBT docs serve, captures lineage and metadata for visualization" {
                webApp = component "webApp" "Web application for visualizing data lineage and execution history"
                dbtArtifacts = component "DBT Artifacts" "Compilled Artifacts"

                webApp -> dbtArtifacts "Uses compiled DBT artifacts for lineage and metadata"
            }
        }

        // Container and system relationships
        // This section defines how actors, DWA containers, and external systems interact
        // user -> edhDatabase "Reads analytics data from"

        dataEngineer -> metadataStore "Provides metadata and source schema"
        metadataStore -> projectBuilder "Supplies metadata"
        projectBuilder -> projectRunner "Provides generated DBT project"
        projectRunner -> entityRelationship "Generates Artifacts for lineage and documentation"
        projectRunner -> edhDatabase "Writes vault and analytics data to"
        projectRunner -> sourceSystems "Uses source data from"
        // projectRunner -> auditLog "Writes execution and lineage events"
        dwa -> databricks "Runs on"
    }

    // View definitions for the DWA architecture
    views {
        // System context view shows the overall DWA system and its users/external systems
        systemContext dwa "SystemContext" {
            include *
            // autoLayout lr
        }

        // Container view shows the DWA containers and the main actors/external systems they interact with
        container dwa "Container" {
            include dataEngineer
            // include user
            include sourceSystems
            include metadataStore
            include projectBuilder
            include projectRunner
            include entityRelationship
            autoLayout lr
        }

        // Component view for the Metadata Store, showing detailed metadata configuration elements
        component metadataStore "MetadataStoreComponents" {
            include systemsConfig
            include tablesConfig
            // include columnsConfig
            include stagingConfig
            include rawVaultConfig
            include martsConfig
            include testsConfig
            autoLayout lr
        }

        // Component view for the DataVault Builder, showing internal generation components
        component projectBuilder "DataVaultBuilderComponents" {
            include metadataReader
            include validator
            include parser
            include hubGenerator
            include linkGenerator
            include satelliteGenerator
            include macroGenerator
            include testGenerator
            include configGenerator
            include fileWriter
            autoLayout lr
        }

        // Component view for the DataVault Runner, showing execution and storage components
        component projectRunner "DataVaultRunnerComponents" {
            include dbtEngine
            include rawVault
            include pitLayer
            include starSchema
            include auditLog
            autoLayout lr
        }

        // Dynamic view shows the runtime flow of a DWA execution pipeline
        dynamic dwa "RunPipeline" {
            dataEngineer -> metadataStore "1. Configure metadata"
            metadataStore -> projectBuilder "2. Trigger metadata-driven generation"
            // scheduler -> projectRunner "3. Trigger run"
            projectBuilder -> projectRunner "4. Provide generated DBT project"
            // projectRunner -> databricks "5. Execute on Databricks"
            projectRunner -> edhDatabase "6. Persist output to Enterprise Data Hub"
            // projectRunner -> user "7. Provide analytics output"
        }

        // Deployment view is commented out; it can be enabled once runtime nodes are finalized
        // deployment "Deployment View" {
        //     environment production "Production" {
        //         deploymentNode databricksNode "Databricks Workspace" "Managed cloud analytics workspace" {
        //             deploymentNode cluster "DBT Execution Cluster" "Spark cluster for DBT and Delta execution" {
        //                 deploymentNode appNode "DWA App" "Python and DBT runtime environment" {
        //                     uses projectBuilder "Generates DBT artifacts"
        //                     uses projectRunner "Executes DBT runs"
        //                 }
        //             }

        //             deploymentNode datalake "Delta Lake Storage" "Delta Lake storage for raw vault, PIT, star schema, and audit data" {
        //                 uses edhDatabase "Stores vault and analytics tables"
        //             }
        //         }

        //         deploymentNode repo "Git Repository" "Source control for metadata, DBT project, and deployment code" {
        //             uses projectBuilder "Contains generation templates and metadata"
        //         }
        //     }
        // }

        // Styles for elements displayed in the views
        styles {
            element "Person" {
                background #1168bd
                color #ffffff
                shape person
            }
            element "Software System" {
                background #438dd5
                color #ffffff
            }
            element "Container" {
                background #85bbf0
                color #000000
            }
            element "Component" {
                background #a2c4f5
                color #000000
            }
            element "Deployment Node" {
                background #999999
                color #ffffff
            }
        }
    }
}
