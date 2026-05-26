export const classify = (v: number): string =>
  v < 0 ? 'neg' : v === 0 ? 'zero' : v === 1 ? 'one'
  : v === 2 ? 'two' : v === 3 ? 'three' : v === 4 ? 'four'
  : v === 5 ? 'five' : v === 6 ? 'six' : v === 7 ? 'seven'
  : v === 8 ? 'eight' : v === 9 ? 'nine' : v === 10 ? 'ten'
  : v === 11 ? 'eleven' : v === 12 ? 'twelve' : 'many';
