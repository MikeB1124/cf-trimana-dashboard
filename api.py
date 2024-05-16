from stacker.blueprints.base import Blueprint
from troposphere import (
    Output,
    Ref,
    s3,
    apigateway
)


class Trimana(Blueprint):

    def create_api_gateway(self):
        t = self.template

        api = apigateway.RestApi(
            "TrimanaDashboardApi",
            Name="trimana-dashboard-api-gateway",
            ApiKeySourceType="HEADER",
            EndpointConfiguration=apigateway.EndpointConfiguration(
                Types=["REGIONAL"]
            )
        )

        t.add_resource(api)

        t.add_output(
            Output(
                "TrimanaDashboardApiId",
                Value=Ref(api),
            )
        )

    def create_template(self):
        self.create_api_gateway()
        return self.template