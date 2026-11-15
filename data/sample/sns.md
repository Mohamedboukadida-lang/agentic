# Amazon SNS

> Sample study notes for the offline demo. Simplified and written for this project; check the AWS documentation for current limits.

Amazon Simple Notification Service (SNS) is a managed publish and subscribe service. A publisher sends a message to a topic and SNS pushes a copy to every subscriber of that topic.

## Subscribers

A topic can deliver to SQS queues, Lambda functions, HTTP and HTTPS endpoints, email addresses, SMS and Amazon Data Firehose. SNS is push based: subscribers do not poll.

## Fan-out pattern

In the fan-out pattern one SNS topic has several SQS queues subscribed to it. Each queue receives its own copy of every message, so independent consumers can process the same event at their own pace. This is the usual way to send one event to many services.

## Message filtering

A subscription filter policy lets a subscriber receive only the messages whose attributes or body match the policy. Filtering happens inside SNS, so unwanted messages are never delivered.

## FIFO topics

A FIFO topic preserves message order and deduplicates messages. A FIFO topic delivers to SQS FIFO queues.
