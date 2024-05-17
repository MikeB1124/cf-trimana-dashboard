from stacker.blueprints.base import Blueprint
from troposphere import (
    Ref,
    GetAtt,
    iam,
    awslambda,
    Parameter,
    Sub,
    apigateway,
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
                ],
            )
        )

        trimana_dashboard_lambda_function = awslambda.Function(
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
            Handler="handler",
            Runtime="provided.al2023",
            Role=GetAtt(lambda_role, "Arn"),
        )
        self.template.add_resource(trimana_dashboard_lambda_function)

        self.template.add_resource(
            awslambda.Permission(
                "TrimanaDashboardLambdaInvokePermission",
                DependsOn=trimana_dashboard_lambda_function,
                Action="lambda:InvokeFunction",
                FunctionName=self.get_variables()["env-dict"][
                    "TrimanaDashboardLambdaName"
                ],
                Principal="apigateway.amazonaws.com",
                SourceArn=Sub(
                    "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiId}/*/GET/poynt/sales",
                    ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                ),
            )
        )

        poynt_sales_api_resource = apigateway.Resource(
            "TrimanaDashboardPoyntSalesResource",
            ParentId="{{resolve:ssm:/trimana/dashboard/poynt/resource/id}}",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="sales",
        )
        self.template.add_resource(poynt_sales_api_resource)

        poynt_sales_api_method = apigateway.Method(
            "TrimanaDashboardPoyntSalesMethod",
            DependsOn=trimana_dashboard_lambda_function,
            AuthorizationType="NONE",
            ApiKeyRequired=True,
            HttpMethod="GET",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            ResourceId=Ref(poynt_sales_api_resource),
            Integration=apigateway.Integration(
                Credentials=GetAtt("TrimanaDashboardLambdaExecutionRole", "Arn"),
                IntegrationHttpMethod="POST",
                Type="AWS_PROXY",
                Uri=Sub(
                    "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations",
                    LambdaArn=GetAtt(trimana_dashboard_lambda_function, "Arn"),
                ),
            ),
        )
        self.template.add_resource(poynt_sales_api_method)

    def create_template(self):
        self.get_existing_trimana_bucket()
        self.create_trimana_dashboard_lambda()
        return self.template
