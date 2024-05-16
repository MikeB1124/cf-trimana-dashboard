from stacker.blueprints.base import Blueprint
from troposphere import (
    Template,
    Ref,
    GetAtt,
    iam,
    awslambda,
    Parameter,
    Sub,
    apigateway,
    ssm,
)


class TrimanaDashboardLambdas(Blueprint):

    def create_trimana_dashboard_lambda(self):
        t = self.template

        existing_trimana_bucket = t.add_parameter(
            Parameter(
                "S3Bucket",
                Type="String",
                Default="trimana-dashboard-bucket",
            )
        )

        lambda_role = t.add_resource(
            iam.Role(
                "LambdaExecutionRole",
                AssumeRolePolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": ["lambda.amazonaws.com"]},
                            "Action": ["sts:AssumeRole"],
                        }
                    ],
                },
                Policies=[
                    iam.Policy(
                        PolicyName="LambdaS3Policy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["s3:GetObject"],
                                    "Resource": [Sub("arn:aws:s3:::${S3Bucket}/*")],
                                }
                            ],
                        },
                    ),
                    iam.Policy(
                        PolicyName="LambdaLogPolicy",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "logs:CreateLogGroup",
                                    "Resource": "arn:aws:logs:us-west-2:934985413136:*",
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "logs:CreateLogStream",
                                        "logs:PutLogEvents",
                                    ],
                                    "Resource": [
                                        "arn:aws:logs:us-west-2:934985413136:log-group:/aws/lambda/trimana-dashboard-api:*"
                                    ],
                                },
                            ],
                        },
                    ),
                ],
            )
        )

        t.add_resource(
            awslambda.Function(
                "LambdaFunction",
                FunctionName="trimana-dashboard-api",
                Code=awslambda.Code(
                    S3Bucket=Ref(existing_trimana_bucket),
                    S3Key="lambdas/trimana-dashboard-api.zip",
                ),
                Handler="handler",
                Runtime="provided.al2023",
                Role=GetAtt(lambda_role, "Arn"),
            )
        )

        api_resource = apigateway.Resource(
            "TrimanaDashboardHelloResource",
            ParentId=GetAtt(
                "{{resolve:ssm:/trimana/dashboard/api/id:1}}", "RootResourceId"
            ),
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id:1}}",
            PathPart="hello",
        )
        t.add_resource(api_resource)

    def create_template(self):
        self.create_trimana_dashboard_lambda()
        return self.template
