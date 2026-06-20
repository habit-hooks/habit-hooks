# From sample calls

sample_sensor.json

```json
{
  "issues": [
    {
      "smell": "issue56"
    }
  ]
}
```

sample_guides.ts

```ts
export default {
  "issue56" : (details) => {
    return prompt("Fix issue56");
  }
}
```

sample_guides.ts

```ts
export default {
  "issue56" : (details) => {
    return run("Fixissue56.sh")
  }
}
```

```bash
cat sample_sensor.json | mapper --guides ./sample_guides.ts
```

```
 ❌ Fix issue56
```

# Alternatives

issue56.ts

```ts
(details) => {
    return prompt("Fix issue56");
  }
```

issue56.md

```markdown
Fix issue56
```

# Plugability

## events

begin all
begin guide
end guide
end all


# Complete pipeline

```bash

combine --sensors sample_config.json | mapper 

```