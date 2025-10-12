from stacker.blueprints.base import Blueprint
from troposphere import (
    Ref,
    GetAtt,
    iam,
    awslambda,
    Parameter,
    Sub,
    apigateway,
    scheduler,
)


class Trimana(Blueprint):
    VARIABLES = {"env-dict": {"type": dict}}

    def create_cors_method(self, resource_name, resource_id, rest_api_id):
        """Helper function to create OPTIONS method for CORS preflight"""
        cors_method = apigateway.Method(
            f"{resource_name}CorsMethod",
            AuthorizationType="NONE",
            ApiKeyRequired=False,
            HttpMethod="OPTIONS",
            RestApiId=rest_api_id,
            ResourceId=resource_id,
            Integration=apigateway.Integration(
                Type="MOCK",
                IntegrationResponses=[
                    apigateway.IntegrationResponse(
                        StatusCode="200",
                        ResponseParameters={
                            "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                            "method.response.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                        ResponseTemplates={
                            "application/json": ""
                        }
                    )
                ],
                PassthroughBehavior="WHEN_NO_MATCH",
                RequestTemplates={
                    "application/json": '{"statusCode": 200}'
                }
            ),
            MethodResponses=[
                apigateway.MethodResponse(
                    StatusCode="200",
                    ResponseParameters={
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                    ResponseModels={
                        "application/json": "Empty"
                    }
                )
            ],
        )
        return cors_method

    def get_existing_trimana_bucket(self):
        self.existing_trimana_bucket = self.template.add_parameter(
            Parameter(
                "TrimanaDashboardS3Bucket",
                Type="String",
                Default=self.get_variables()["env-dict"]["BucketName"],
            )
        )

    def create_trimana_dashboard_lambda(self):
        lambda_role = self.template.add_resource(
            iam.Role(
                "TrimanaDashboardLambdaExecutionRole",
                AssumeRolePolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "Service": [
                                    "lambda.amazonaws.com",
                                    "apigateway.amazonaws.com",
                                ]
                            },
                            "Action": ["sts:AssumeRole"],
                        }
                    ],
                },
                Policies=[
                    iam.Policy(
                        PolicyName="TrimanaDashboardLambdaS3Policy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["s3:GetObject"],
                                    "Resource": [
                                        Sub(
                                            "arn:aws:s3:::${BucketName}/*",
                                            BucketName=self.get_variables()["env-dict"][
                                                "BucketName"
                                            ],
                                        )
                                    ],
                                }
                            ],
                        },
                    ),
                    iam.Policy(
                        PolicyName="TrimanaDashboardLambdaLogPolicy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "logs:CreateLogGroup",
                                    "Resource": Sub(
                                        "arn:aws:logs:${AWS::Region}:${AWS::AccountId}:*"
                                    ),
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "logs:CreateLogStream",
                                        "logs:PutLogEvents",
                                    ],
                                    "Resource": [
                                        Sub(
                                            "arn:aws:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${LambdaName}:*",
                                            LambdaName=self.get_variables()["env-dict"][
                                                "TrimanaDashboardLambdaName"
                                            ],
                                        )
                                    ],
                                },
                            ],
                        },
                    ),
                    iam.Policy(
                        PolicyName="TrimanaDashboardLambdaSecretsManagerPolicy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["secretsmanager:GetSecretValue"],
                                    "Resource": [
                                        Sub(
                                            "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${SecretId}-yuRaM1",
                                            SecretId=self.get_variables()["env-dict"][
                                                "SharedSecretsId"
                                            ],
                                        )
                                    ],
                                }
                            ],
                        },
                    ),
                ],
            )
        )

        self.trimana_dashboard_lambda_function = awslambda.Function(
            "TrimanaDashboardLambdaFunction",
            FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
            Code=awslambda.Code(
                S3Bucket=Ref(self.existing_trimana_bucket),
                S3Key=Sub(
                    "lambdas/${LambdaName}.zip",
                    LambdaName=self.get_variables()["env-dict"][
                        "TrimanaDashboardLambdaName"
                    ],
                ),
            ),
            Environment=awslambda.Environment(
                Variables={
                    "SHARED_SECRETS": self.get_variables()["env-dict"][
                        "SharedSecretsId"
                    ]
                }
            ),
            Handler="handler",
            Runtime="provided.al2023",
            Timeout=60,
            Role=GetAtt(lambda_role, "Arn"),
        )
        self.template.add_resource(self.trimana_dashboard_lambda_function)
    
    def create_auth_endpoints(self):
        """Create authentication endpoints"""
        # /auth resource
        auth_resource = apigateway.Resource(
            "TrimanaDashboardAuthResource",
            ParentId="{{resolve:ssm:/trimana/dashboard/api/parent/resource/id}}",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="auth",
        )
        self.template.add_resource(auth_resource)
        
        # /auth/login resource
        auth_login_resource = apigateway.Resource(
            "TrimanaDashboardAuthLoginResource",
            ParentId=Ref(auth_resource),
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="login",
        )
        self.template.add_resource(auth_login_resource)
        
        # POST /auth/login method (no API key required for login)
        auth_login_method = apigateway.Method(
            "TrimanaDashboardAuthLoginMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=False,
            HttpMethod="POST",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(auth_login_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(auth_login_method)
        
        # OPTIONS /auth/login for CORS
        auth_login_cors = self.create_cors_method(
            "TrimanaDashboardAuthLogin",
            Ref(auth_login_resource),
            "{{resolve:ssm:/trimana/dashboard/api/id}}"
        )
        self.template.add_resource(auth_login_cors)
        
        # Lambda permission for auth/login
        self.template.add_resource(
            awslambda.Permission(
                "AuthLoginLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/POST/auth/login",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
    
    def create_employee_endpoints(self):
        """Create employee CRUD endpoints"""
        # /employees resource
        employees_resource = apigateway.Resource(
            "TrimanaDashboardEmployeesResource",
            ParentId="{{resolve:ssm:/trimana/dashboard/api/parent/resource/id}}",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="employees",
        )
        self.template.add_resource(employees_resource)
        
        # GET /employees method
        employees_get_method = apigateway.Method(
            "TrimanaDashboardEmployeesGetMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="GET",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(employees_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(employees_get_method)
        
        # POST /employees method
        employees_post_method = apigateway.Method(
            "TrimanaDashboardEmployeesPostMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="POST",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(employees_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(employees_post_method)
        
        # OPTIONS /employees for CORS
        employees_cors = self.create_cors_method(
            "TrimanaDashboardEmployees",
            Ref(employees_resource),
            "{{resolve:ssm:/trimana/dashboard/api/id}}"
        )
        self.template.add_resource(employees_cors)
        
        # /employees/{id} resource
        employee_id_resource = apigateway.Resource(
            "TrimanaDashboardEmployeeIdResource",
            ParentId=Ref(employees_resource),
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="{id}",
        )
        self.template.add_resource(employee_id_resource)
        
        # GET /employees/{id} method
        employee_get_method = apigateway.Method(
            "TrimanaDashboardEmployeeGetMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="GET",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(employee_id_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(employee_get_method)
        
        # PUT /employees/{id} method
        employee_put_method = apigateway.Method(
            "TrimanaDashboardEmployeePutMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="PUT",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(employee_id_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(employee_put_method)
        
        # DELETE /employees/{id} method
        employee_delete_method = apigateway.Method(
            "TrimanaDashboardEmployeeDeleteMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="DELETE",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(employee_id_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(employee_delete_method)
        
        # OPTIONS /employees/{id} for CORS
        employee_id_cors = self.create_cors_method(
            "TrimanaDashboardEmployeeId",
            Ref(employee_id_resource),
            "{{resolve:ssm:/trimana/dashboard/api/id}}"
        )
        self.template.add_resource(employee_id_cors)
        
        # Lambda permissions for employee endpoints
        self.template.add_resource(
            awslambda.Permission(
                "EmployeesGetLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/GET/employees",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
        
        self.template.add_resource(
            awslambda.Permission(
                "EmployeesPostLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/POST/employees",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
        
        self.template.add_resource(
            awslambda.Permission(
                "EmployeeGetLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/GET/employees/*",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
        
        self.template.add_resource(
            awslambda.Permission(
                "EmployeePutLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/PUT/employees/*",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
        
        self.template.add_resource(
            awslambda.Permission(
                "EmployeeDeleteLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/DELETE/employees/*",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
    
    def create_timecard_endpoints(self):
        """Create timecard CRUD endpoints"""
        # /timecards resource
        timecards_resource = apigateway.Resource(
            "TrimanaDashboardTimecardsResource",
            ParentId="{{resolve:ssm:/trimana/dashboard/api/parent/resource/id}}",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="timecards",
        )
        self.template.add_resource(timecards_resource)
        
        # GET /timecards method
        timecards_get_method = apigateway.Method(
            "TrimanaDashboardTimecardsGetMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="GET",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(timecards_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(timecards_get_method)
        
        # POST /timecards method
        timecards_post_method = apigateway.Method(
            "TrimanaDashboardTimecardsPostMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="POST",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(timecards_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(timecards_post_method)
        
        # OPTIONS /timecards for CORS
        timecards_cors = self.create_cors_method(
            "TrimanaDashboardTimecards",
            Ref(timecards_resource),
            "{{resolve:ssm:/trimana/dashboard/api/id}}"
        )
        self.template.add_resource(timecards_cors)
        
        # /timecards/{id} resource
        timecard_id_resource = apigateway.Resource(
            "TrimanaDashboardTimecardIdResource",
            ParentId=Ref(timecards_resource),
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="{id}",
        )
        self.template.add_resource(timecard_id_resource)
        
        # GET /timecards/{id} method
        timecard_get_method = apigateway.Method(
            "TrimanaDashboardTimecardGetMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="GET",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(timecard_id_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(timecard_get_method)
        
        # PUT /timecards/{id} method
        timecard_put_method = apigateway.Method(
            "TrimanaDashboardTimecardPutMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="PUT",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(timecard_id_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(timecard_put_method)
        
        # DELETE /timecards/{id} method
        timecard_delete_method = apigateway.Method(
            "TrimanaDashboardTimecardDeleteMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="DELETE",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(timecard_id_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(timecard_delete_method)
        
        # OPTIONS /timecards/{id} for CORS
        timecard_id_cors = self.create_cors_method(
            "TrimanaDashboardTimecardId",
            Ref(timecard_id_resource),
            "{{resolve:ssm:/trimana/dashboard/api/id}}"
        )
        self.template.add_resource(timecard_id_cors)
        
        # Lambda permissions for timecard endpoints
        self.template.add_resource(
            awslambda.Permission(
                "TimecardsGetLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/GET/timecards",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
        
        self.template.add_resource(
            awslambda.Permission(
                "TimecardsPostLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/POST/timecards",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
        
        self.template.add_resource(
            awslambda.Permission(
                "TimecardGetLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/GET/timecards/*",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
        
        self.template.add_resource(
            awslambda.Permission(
                "TimecardPutLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/PUT/timecards/*",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
        
        self.template.add_resource(
            awslambda.Permission(
                "TimecardDeleteLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"]["TrimanaDashboardLambdaName"],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/DELETE/timecards/*",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )
    
    def create_payroll_endpoints(self):
        """Create original payroll event and report endpoints"""
        payroll_event_api_resource = apigateway.Resource(
            "TrimanaDashboardPayrollEventResource",
            ParentId="{{resolve:ssm:/trimana/dashboard/payroll/resource/id}}",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="event",
        )
        self.template.add_resource(payroll_event_api_resource)

        payroll_report_api_resource = apigateway.Resource(
            "TrimanaDashboardPayrollReportResource",
            ParentId="{{resolve:ssm:/trimana/dashboard/payroll/resource/id}}",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="report",
        )
        self.template.add_resource(payroll_report_api_resource)

        payroll_event_api_method = apigateway.Method(
            "TrimanaDashboardPayrollEventMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="POST",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(payroll_event_api_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(payroll_event_api_method)

        payroll_report_api_method = apigateway.Method(
            "TrimanaDashboardPayrollReportMethod",
            DependsOn=self.trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="POST",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(payroll_report_api_resource),
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(payroll_report_api_method)

        self.template.add_resource(
            awslambda.Permission(
                "PayrollEventLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"][
                    "TrimanaDashboardLambdaName"
                ],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/POST/payroll/event",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )

        self.template.add_resource(
            awslambda.Permission(
                "PayrollReportLambdaInvokePermission",
                DependsOn=self.trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"][
                    "TrimanaDashboardLambdaName"
                ],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/POST/payroll/report",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )

    def create_payroll_report_scheduler(self):
        scheduler_execution_role = self.template.add_resource(
            iam.Role(
                "PayrollReportSchedulerExecutionRole",
                AssumeRolePolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "scheduler.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                },
                Policies=[
                    iam.Policy(
                        PolicyName="PayrollReportSchedulerExecutionPolicy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["lambda:InvokeFunction"],
                                    "Resource": "*",
                                },
                            ],
                        },
                    )
                ],
            )
        )

        payroll_report_sync_scheduler = scheduler.Schedule(
            "PayrollReportScheduler",
            Name="payroll-report-scheduler",
            Description="Payroll Report Scheduler",
            ScheduleExpression="cron(0 17 ? * * *)",
            ScheduleExpressionTimezone="America/Los_Angeles",
            FlexibleTimeWindow=scheduler.FlexibleTimeWindow(Mode="OFF"),
            Target=scheduler.Target(
                Arn=GetAtt(self.trimana_dashboard_lambda_function, "Arn"),
                Input='{"httpMethod": "POST", "path": "/payroll/report"}',
                RetryPolicy=scheduler.RetryPolicy(
                    MaximumEventAgeInSeconds=86400, MaximumRetryAttempts=185
                ),
                RoleArn=GetAtt(scheduler_execution_role, "Arn"),
            ),
        )
        self.template.add_resource(payroll_report_sync_scheduler)
    
    def create_twilio_alert_lambda(self):
        lambda_role = self.template.add_resource(
            iam.Role(
                "TwilioAlertLambdaExecutionRole",
                AssumeRolePolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "Service": [
                                    "lambda.amazonaws.com",
                                    "apigateway.amazonaws.com",
                                ]
                            },
                            "Action": ["sts:AssumeRole"],
                        }
                    ],
                },
                Policies=[
                    iam.Policy(
                        PolicyName="TwilioAlertLambdaS3Policy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["s3:GetObject"],
                                    "Resource": [
                                        Sub(
                                            "arn:aws:s3:::${BucketName}/*",
                                            BucketName=self.get_variables()["env-dict"][
                                                "BucketName"
                                            ],
                                        )
                                    ],
                                }
                            ],
                        },
                    ),
                    iam.Policy(
                        PolicyName="TwilioAlertLambdaLogPolicy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "logs:CreateLogGroup",
                                    "Resource": Sub(
                                        "arn:aws:logs:${AWS::Region}:${AWS::AccountId}:*"
                                    ),
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "logs:CreateLogStream",
                                        "logs:PutLogEvents",
                                    ],
                                    "Resource": [
                                        Sub(
                                            "arn:aws:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${LambdaName}:*",
                                            LambdaName=self.get_variables()["env-dict"][
                                                "TwilioAlertLambdaName"
                                            ],
                                        )
                                    ],
                                },
                            ],
                        },
                    ),
                    iam.Policy(
                        PolicyName="TwilioAlertLambdaSecretsManagerPolicy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["secretsmanager:GetSecretValue"],
                                    "Resource": [
                                        Sub(
                                            "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${SecretId}-yuRaM1",
                                            SecretId=self.get_variables()["env-dict"][
                                                "SharedSecretsId"
                                            ],
                                        )
                                    ],
                                }
                            ],
                        },
                    ),
                ],
            )
        )

        self.twilio_alert_lambda_function = awslambda.Function(
            "TwilioAlertLambdaFunction",
            FunctionName=self.get_variables()["env-dict"]["TwilioAlertLambdaName"],
            Code=awslambda.Code(
                S3Bucket=Ref(self.existing_trimana_bucket),
                S3Key="lambdas/twilio-alert.zip"
            ),
            Environment=awslambda.Environment(
                Variables={
                    "SHARED_SECRETS": self.get_variables()["env-dict"][
                        "SharedSecretsId"
                    ]
                }
            ),
            Handler="handler",
            Runtime="provided.al2023",
            Timeout=60,
            Role=GetAtt(lambda_role, "Arn"),
        )
        self.template.add_resource(self.twilio_alert_lambda_function)

        twilio_alert_api_method = apigateway.Method(
            "TwilioAlertMethod",
            DependsOn=self.twilio_alert_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="POST",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId="{{resolve:ssm:/trimana/dashboard/alert/resource/id}}",
            Integration=apigateway.Integration(
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(self.twilio_alert_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(twilio_alert_api_method)

        self.template.add_resource(
            awslambda.Permission(
                "TwilioAlertLambdaInvokePermission",
                DependsOn=self.twilio_alert_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"][
                    "TwilioAlertLambdaName"
                ],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/POST/alert",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )

    def create_twilio_alert_scheduler(self):
        scheduler_execution_role = self.template.add_resource(
            iam.Role(
                "TwilioAlertSchedulerExecutionRole",
                AssumeRolePolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "scheduler.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                },
                Policies=[
                    iam.Policy(
                        PolicyName="TwilioAlertSchedulerExecutionPolicy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["lambda:InvokeFunction"],
                                    "Resource": "*",
                                },
                            ],
                        },
                    )
                ],
            )
        )

        twilio_alert_scheduler = scheduler.Schedule(
            "TwilioAlertScheduler",
            Name="twilio-alert-scheduler",
            Description="Schedule Twilio Alert",
            ScheduleExpression="cron(0 19 ? * * *)",
            ScheduleExpressionTimezone="America/Los_Angeles",
            FlexibleTimeWindow=scheduler.FlexibleTimeWindow(Mode="OFF"),
            Target=scheduler.Target(
                Arn=GetAtt(self.twilio_alert_lambda_function, "Arn"),
                Input='{"httpMethod": "POST", "path": "/alert", "body": "{\\"announcement\\": \\"Please double check clock in and clock out timesheets for thata and papu.\\", \\"from_number\\": \\"+17755876906\\", \\"to_numbers\\": [\\"+18186895373\\", \\"+18189156894\\", \\"+18188099978\\"]}"}',
                RetryPolicy=scheduler.RetryPolicy(
                    MaximumEventAgeInSeconds=86400, MaximumRetryAttempts=185
                ),
                RoleArn=GetAtt(scheduler_execution_role, "Arn"),
            ),
        )
        self.template.add_resource(twilio_alert_scheduler)

    def create_template(self):
        self.get_existing_trimana_bucket()
        self.create_trimana_dashboard_lambda()
        self.create_auth_endpoints()
        self.create_employee_endpoints()
        self.create_timecard_endpoints()
        self.create_payroll_endpoints()
        self.create_payroll_report_scheduler()
        self.create_twilio_alert_lambda()
        self.create_twilio_alert_scheduler()
        return self.template
