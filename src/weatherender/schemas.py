from marshmallow import Schema, fields, validate


class CityRequestSchema(Schema):
    city = fields.Str(required=True, validate=validate.Length(min=1, max=100))
