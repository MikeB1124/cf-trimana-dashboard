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

    def create_template(self):
        trimana_dashboard_api_deoployment = self.template.add_resource(
            apigateway.Deployment(
                "TrimanaDashboardApiDeployment",
                RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
            )
        )

        trimana_dashboard_api_stage = self.template.add_resource(
            apigateway.Stage(
                "TrimanaDashboardApiStage",
                DeploymentId=Ref(trimana_dashboard_api_deoployment),
                RestApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                StageName="api",
            )
        )

        trimana_dashboard_usage_plan = self.template.add_resource(
            apigateway.UsagePlan(
                "TrimanaDashboardUsagePlan",
                DependsOn=trimana_dashboard_api_stage,
                UsagePlanName=self.get_variables()["env-dict"]["ApiUsagePlanName"],
                ApiStages=[
                    apigateway.ApiStage(
                        ApiId="{{resolve:ssm:/trimana/dashboard/api/id}}",
                        Stage="api",
                    )
                ],
                Description="Trimana Dashboard Usage Plan",
                Quota=apigateway.QuotaSettings(
                    Limit=100000,
                    Period="MONTH",
                ),
                Throttle=apigateway.ThrottleSettings(
                    BurstLimit=100,
                    RateLimit=50,
                ),
            )
        )

        trimana_dashboard_api_key = self.template.add_resource(
            apigateway.ApiKey(
                "TrimanaDashboardApiKey",
                Name=self.get_variables()["env-dict"]["ApiKeyName"],
            )
        )

        self.template.add_resource(
            apigateway.UsagePlanKey(
                "TrimanaDashboardUsagePlanKey",
                DependsOn=trimana_dashboard_usage_plan,
                KeyId=Ref(trimana_dashboard_api_key),
                KeyType="API_KEY",
                UsagePlanId=Ref(trimana_dashboard_usage_plan),
            )
        )
