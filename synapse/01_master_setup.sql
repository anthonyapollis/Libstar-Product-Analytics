-- Run against the SERVERLESS endpoint, database: master
-- syn-pargoparcels-ondemand.sql.azuresynapse.net
-- Passwords are substituted by deploy_synapse.ps1 ($(QLIK_READER_PWD)).

IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = 'libstar')
    EXEC('CREATE DATABASE libstar COLLATE Latin1_General_100_BIN2_UTF8');
GO

IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'qlik_reader')
    EXEC('CREATE LOGIN qlik_reader WITH PASSWORD = ''$(QLIK_READER_PWD)''');
GO
