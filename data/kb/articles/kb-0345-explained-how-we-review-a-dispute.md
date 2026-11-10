---
doc_id: kb-0345
title: "Explained: how we review a dispute"
category: refunds_disputes
section_path: [Guides, Explained]
countries: all
effective_date: 2025-01-01
superseded_by: null
article_type: guide
status: draft
mess: [buried_exception, cross_reference]
---
When you open a dispute, it can feel as if it disappears into a black box. Here's what actually happens between the moment you tap **Submit** and the moment you get a decision.

## Step 1: we check what kind of problem it is

Every dispute is first sorted by type, because each type follows different rules:

- **A transfer sent to the wrong person.** We contact the recipient, or the recipient's bank.
- **A card payment where something went wrong with the merchant**, such as goods that never arrived, a cancelled service or a double charge. These can go to the card network as a chargeback.
- **A payment you didn't make.** This isn't really a dispute. It's handled under our rules for unauthorized transactions, which give you stronger protection. See [Transactions I didn't make](kb-0090).

If you chose the wrong type when you reported it, we move it to the right process. You don't need to report it again.

## Step 2: we look at the evidence

We read what you've told us and look at the payment details on our side: when it was made, how it was approved, which device was used, and whether the merchant has already sent a refund.

This is why evidence matters. For card disputes, the merchant's bank will ask us for proof, and a dispute with screenshots of the order, the merchant's replies and the delivery date is much stronger than one without. See [Evidence to include in a dispute](kb-0087).

## Step 3: we contact the other side

- For wrong transfers to another Sahla Pay user, we ask the recipient to return the money. We can't take it from their account without their agreement, unless the law allows it.
- For wrong transfers to a bank account, we ask the receiving bank. The bank makes the final decision.
- For card disputes, we send a chargeback through the card network. The merchant then has a period set by the network to respond.

## Step 4: temporary credit

For card disputes, if the case is still open after {{dispute.temporary_credit_after.ALL}}, we usually add a temporary credit to your balance. If the dispute is later decided in the merchant's favour, the credit is taken back. For wrong transfers between users, there's no temporary credit; you get the money only if it can be recovered.

## Step 5: the decision

You get the decision in the app and by email. If the dispute is approved, the money is returned within the times in [Refund timelines](kb-0071). If it's rejected, we explain why.

## If you disagree

You can appeal once, within {{dispute.appeal_window.ALL}} of the decision, if you have new information. A second appeal with the same evidence is closed without a new review. See [My dispute was rejected](kb-0086).
