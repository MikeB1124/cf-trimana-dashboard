from stacker.blueprints.base import Blueprint
from troposphere import Output, Ref, s3, apigateway, GetAtt, ssm


class Trimana(Blueprint):
    VARIABLES = {"env-dict": {"type": dict}}

    def create_api_gateway(self):
        self.api = apigateway.RestApi(
            "TrimanaDashboardApi",
            Name=self.get_variables()["env-dict"]["ApiName"],
            ApiKeySourceType="HEADER",
            EndpointConfiguration=apigateway.EndpointConfiguration(Types=["REGIONAL"]),
        )
        self.template.add_resource(self.api)

        self.template.add_output(
            Output(
                "TrimanaDashboardApiId",
                Value=Ref(self.api),
            )
        )

    def store_ssm_parameters(self):
        ssm_api_id = ssm.Parameter(
            "TrimanaDashboardApiId",
            Name="/trimana/dashboard/api/id",
            Type="String",
            Value=Ref(self.api),
        )
        self.template.add_resource(ssm_api_id)

        ssm_api_parent_resource_id = ssm.Parameter(
            "TrimanaDashboardApiParentResourceId",
            Name="/trimana/dashboard/api/parent/resource/id",
            Type="String",
            Value=GetAtt(self.api, "RootResourceId"),
        )
        self.template.add_resource(ssm_api_parent_resource_id)

    def create_template(self):
        self.create_api_gateway()
        self.store_ssm_parameters()
        return self.template
