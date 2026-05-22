import { BasuraPage } from './app.po';

describe('basura App', () => {
  let page: BasuraPage;

  beforeEach(() => {
    page = new BasuraPage();
  });

  it('should display message saying app works', () => {
    page.navigateTo();
    expect(page.getParagraphText()).toEqual('app works!');
  });
});
