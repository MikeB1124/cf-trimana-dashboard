from stacker.blueprints.base import Blueprint
from troposphere import Template, Ref, GetAtt, iam, awslambda, Parameter, Sub


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
                    )
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

    def create_template(self):
        self.create_trimana_dashboard_lambda()
        return self.template
