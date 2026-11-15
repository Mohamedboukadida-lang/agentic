# Amazon EventBridge

> Sample study notes for the offline demo. Simplified and written for this project; check the AWS documentation for current limits.

Amazon EventBridge is a serverless event bus. It receives events from AWS services, your own applications and partner software, and routes them to targets according to rules.

## Event buses

Every account has a default event bus that receives events from AWS services. You can create custom event buses for your own applications and partner event buses for software vendors.

## Rules and targets

A rule matches incoming events against an event pattern, a JSON document that describes which events to select by their fields. A matched event is sent to the targets of the rule, such as a Lambda function, an SQS queue or a Step Functions state machine. One rule can have up to 5 targets.

## Scheduling

EventBridge Scheduler runs tasks on a schedule. A schedule uses a cron expression, a rate expression or a single date and time. This is the usual way to start a job every night without running a server.

## Archive and replay

An archive stores events from a bus. A replay sends archived events to the bus again, which helps to test a fix or recover from a bug in a consumer.

## Routing compared with a queue

EventBridge routes each event by its content to the targets that asked for it. It does not hold messages for consumers to poll. When a consumer needs buffering and retries at its own pace, put an SQS queue behind the rule as the target.
