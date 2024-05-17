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
                            "Principal": {"Service": ["lambda.amazonaws.com"]},
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
                                    "Resource": Sub("arn:aws:logs:${AWS::Region}:${AWS::AccountId}:*"),
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
                                                "LambdaName"
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

        self.template.add_resource(
            awslambda.Function(
                "TrimanaDashboardLambdaFunction",
                FunctionName=self.get_variables()["env-dict"]["LambdaName"],
                Code=awslambda.Code(
                    S3Bucket=Ref(self.existing_trimana_bucket),
                    S3Key=Sub(
                        "lambdas/${LambdaName}.zip",
                        LambdaName=self.get_variables()["env-dict"]["LambdaName"],
                    ),
                ),
                Handler="handler",
                Runtime="provided.al2023",
                Role=GetAtt(lambda_role, "Arn"),
            )
        )

        api_resource = apigateway.Resource(
            "TrimanaDashboardHelloResource",
            ParentId="{{resolve:ssm:/trimana/dashboard/api/parent/resource/id}}",
            RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            PathPart="hello",
        )
        self.template.add_resource(api_resource)

    def create_template(self):
        self.get_existing_trimana_bucket()
        self.create_trimana_dashboard_lambda()
        return self.template
