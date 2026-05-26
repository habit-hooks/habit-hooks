export class WithUnusedMember {
  used(): number {
    return 1;
  }
  unused(): number {
    return 2;
  }
}
