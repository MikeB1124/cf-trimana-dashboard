from stacker.blueprints.base import Blueprint
from troposphere import (
    Output,
    Ref,
    s3,
)


class LambdaBucket(Blueprint):
    def create_template(self):
        t = self.template

        s3_bucket = s3.Bucket(
            "S3Bucket",
            BucketName="trimana-dashboard-bucket",
        )
        t.add_resource(s3_bucket)

        t.add_output(
            Output(
                "BucketName",
                Value=Ref(s3_bucket),
            )
        )
