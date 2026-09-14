Keep each example focused on one behavior and one clear reason to fail.
Split unrelated expectations into separate examples, sharing setup through
`before`, helpers, or `let` where useful.

Bad — unrelated behavior is bundled into one example:

```ruby
it "creates and announces the account" do
  account = create_account

  expect(account).to be_persisted
  expect(account.plan).to eq("free")
  expect(Mailer).to have_received(:welcome).with(account)
end
```

Good — each behavior has its own example:

```ruby
subject(:create_account) { described_class.call }

it "persists the account" do
  expect(create_account).to be_persisted
end

it "assigns the free plan" do
  expect(create_account.plan).to eq("free")
end

it "sends the welcome email" do
  account = create_account

  expect(Mailer).to have_received(:welcome).with(account)
end
```

Multiple expectations can be appropriate when they jointly describe one
inseparable outcome. Use judgment: improve the test’s focus and diagnostic value;
do not combine assertions, add `aggregate_failures`, or disable the cop merely to
silence RuboCop.

Locations reported:

{% for issue in issues -%}
{{ issue.details.file }}:{{ issue.details.line }} — {{ issue.details.message }}
{% endfor %}
