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
            Role=GetAtt(lambda_role, "Arn"),
        )
        self.template.add_resource(self.trimana_dashboard_lambda_function)

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

    def create_template(self):
        self.get_existing_trimana_bucket()
        self.create_trimana_dashboard_lambda()
        self.create_payroll_report_scheduler()
        return self.template
