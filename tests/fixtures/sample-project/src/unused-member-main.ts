import { WithUnusedMember } from './unused-member.ts';
const x = new WithUnusedMember();
console.log(x.used());
