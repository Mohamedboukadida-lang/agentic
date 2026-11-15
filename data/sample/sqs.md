# Amazon SQS

> Sample study notes for the offline demo. Simplified and written for this project; check the AWS documentation for current limits.

Amazon Simple Queue Service (SQS) is a managed message queue. Producers send messages to a queue and consumers poll the queue to receive them. It decouples the parts of a system so that a slow or failed consumer does not block the producer.

## Queue types

A standard queue offers at-least-once delivery and best-effort ordering. A message can occasionally be delivered more than once, so consumers must be idempotent.

A FIFO queue preserves the order of messages inside a message group and provides exactly-once processing through deduplication. The name of a FIFO queue must end with the suffix .fifo. Without batching, a FIFO queue supports up to 300 API calls per second for each action.

## Visibility timeout

When a consumer receives a message, SQS hides it from other consumers for the visibility timeout. The default visibility timeout is 30 seconds and the maximum is 12 hours. If the consumer does not delete the message before the timeout ends, the message becomes visible again and can be received a second time.

## Message retention

SQS keeps a message for the retention period and then deletes it. The default retention period is 4 days. It can be set from 60 seconds up to 14 days.

## Long polling

Long polling lets a ReceiveMessage call wait for a message to arrive, which reduces empty responses and cost. The wait time is set per request with WaitTimeSeconds or per queue with the ReceiveMessageWaitTimeSeconds attribute. The maximum wait is 20 seconds.

## Dead-letter queues

A dead-letter queue (DLQ) collects messages that could not be processed. The redrive policy of the source queue names the dead-letter queue and sets maxReceiveCount, the number of receives after which a message is moved. A DLQ keeps poison messages from blocking the queue and lets you inspect them later.

## Delay queues

A delay queue postpones delivery of new messages. The delay can be up to 15 minutes.
