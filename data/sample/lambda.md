# AWS Lambda

> Sample study notes for the offline demo. Simplified and written for this project; check the AWS documentation for current limits.

AWS Lambda runs code without servers to manage. You upload a function, an event invokes it, and you pay for the requests and the compute time used.

## Limits

A function can run for at most 900 seconds, which is 15 minutes. Memory can be set from 128 MB to 10,240 MB, and CPU power grows with the memory setting. A zipped deployment package can be up to 50 MB and a container image up to 10 GB.

## Cold starts

When no execution environment is ready, Lambda creates one before it runs the function. This extra latency is called a cold start. Provisioned concurrency keeps environments initialised so that requests avoid cold starts.

## Concurrency

Reserved concurrency sets the maximum number of concurrent instances of a function and guarantees that capacity for it. It also protects downstream systems from too many parallel calls.

## SQS event source

With an event source mapping, Lambda polls an SQS queue and invokes the function with a batch of messages. Set the visibility timeout of the queue to at least six times the function timeout, so a message is not received again while the function is still working on it. Messages that keep failing should go to a dead-letter queue.

## Destinations

For asynchronous invocations, a destination receives the result of the invocation. A failure destination can be an SQS queue, an SNS topic, another Lambda function or an EventBridge event bus.
