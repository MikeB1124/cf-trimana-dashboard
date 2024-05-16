from stacker.blueprints.base import Blueprint
from troposphere import Output, Ref, s3, apigateway, GetAtt, ssm


class Trimana(Blueprint):

    def create_api_gateway(self):
        t = self.template

        api = apigateway.RestApi(
            "TrimanaDashboardApi",
            Name="trimana-dashboard-api-gateway",
            ApiKeySourceType="HEADER",
            EndpointConfiguration=apigateway.EndpointConfiguration(Types=["REGIONAL"]),
        )
        t.add_resource(api)

        ssm_api_id = ssm.Parameter(
            "TrimanaDashboardApiId",
            Name="/trimana/dashboard/api/id",
            Type="String",
            Value=Ref(api),
        )
        t.add_resource(ssm_api_id)

        t.add_output(
            Output(
                "TrimanaDashboardApiId",
                Value=Ref(api),
            )
        )

    def create_template(self):
        self.create_api_gateway()
        return self.template
