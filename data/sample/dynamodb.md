# Amazon DynamoDB

> Sample study notes for the offline demo. Simplified and written for this project; check the AWS documentation for current limits.

Amazon DynamoDB is a managed key-value and document database with single-digit millisecond latency at any scale.

## Keys

Every item is identified by its primary key. A simple primary key is a partition key. A composite primary key is a partition key together with a sort key. DynamoDB uses the partition key to spread items across partitions.

## Item size

The maximum size of an item is 400 KB, including attribute names and values. Store larger objects in Amazon S3 and keep a pointer to them in the item.

## Capacity modes

In on-demand mode you pay per request and DynamoDB adapts to the traffic. In provisioned mode you set read and write capacity units, optionally with auto scaling, which costs less for steady and predictable traffic.

## Secondary indexes

A global secondary index (GSI) has its own partition key and sort key and can be created at any time. A local secondary index (LSI) shares the partition key of the table but has a different sort key, and it must be created together with the table.

## Consistency

Reads are eventually consistent by default. A strongly consistent read returns the latest committed data and uses twice the read capacity.

## Conditional writes

A conditional write succeeds only if a condition expression is true, for example attribute_not_exists on the key. Conditional writes are the standard way to make processing idempotent: writing the same event twice fails the second time and creates no duplicate.

## Streams and TTL

DynamoDB Streams records item changes for 24 hours so that a Lambda function can react to them. Time to Live (TTL) deletes items automatically after a timestamp stored in an attribute.
