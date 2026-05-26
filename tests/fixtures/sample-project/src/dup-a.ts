export function priceA(): number {
  const base = 100;
  const tax = base * 0.1;
  const shipping = base > 100 ? 0 : 10;
  const discount = base > 500 ? base * 0.05 : 0;
  return base + tax + shipping - discount;
}
