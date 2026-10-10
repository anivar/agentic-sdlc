# Good and bad tests

## Good: observable behaviour through the interface

```typescript
test("user can check out with a valid cart", async () => {
  const cart = createCart();
  cart.add(product);
  const result = await checkout(cart, paymentMethod);
  expect(result.status).toBe("confirmed");
});
```

Uses the public interface only. Describes what, not how. Survives internal refactors. One
logical assertion.

## Bad: implementation detail

```typescript
test("checkout calls paymentService.process", async () => {
  const mockPayment = jest.mock(paymentService);
  await checkout(cart, payment);
  expect(mockPayment.process).toHaveBeenCalledWith(cart.total);
});
```

Red flags: mocking internal collaborators, testing private methods, asserting on call counts or
order, a name that describes how rather than what, a test that breaks when a refactor changed no
behaviour.

## Bad: verifying through a side channel

```typescript
test("createUser saves to database", async () => {
  await createUser({ name: "Alice" });
  const row = await db.query("SELECT * FROM users WHERE name = ?", ["Alice"]);
  expect(row).toBeDefined();
});
```

Good: verify through the interface.

```typescript
test("createUser makes the user retrievable", async () => {
  const user = await createUser({ name: "Alice" });
  const retrieved = await getUser(user.id);
  expect(retrieved.name).toBe("Alice");
});
```

## Bad: tautological (TEST-3)

```typescript
test("calculateTotal sums line items", () => {
  const items = [{ price: 10 }, { price: 5 }];
  const expected = items.reduce((sum, i) => sum + i.price, 0);
  expect(calculateTotal(items)).toBe(expected);
});
```

Good: an independent literal, with the derivation when it is not obvious.

```typescript
test("calculateTotal sums line items", () => {
  // 10 + 5 from the worked example in the spec, section 3.1
  expect(calculateTotal([{ price: 10 }, { price: 5 }])).toBe(15);
});
```

## Mocking at boundaries (TEST-4)

Inject the boundary so the test can replace it:

```typescript
function processPayment(order, paymentClient) {
  return paymentClient.charge(order.total);
}
```

Prefer one function per external operation over a generic fetcher, so each mock returns one
shape and a test shows which operations it exercises:

```typescript
const api = {
  getUser: (id) => fetch(`/users/${id}`),
  getOrders: (userId) => fetch(`/users/${userId}/orders`),
};
```
