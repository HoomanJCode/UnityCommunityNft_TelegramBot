/**
 * Tests for the TEP-85 soulbound badge collection (contracts/soulbound/).
 *
 * Soulbound badges are minted directly to the recipient and must NOT be
 * transferable — any Transfer attempt exits with code 1020.
 */
import { toNano, beginCell, Address, Cell } from "@ton/core";

// @ton/core has no emptyCell() export — an empty cell is just `new Cell()`.
const EMPTY_CELL = new Cell();
import {
  Blockchain,
  SandboxContract,
  TreasuryContract,
} from "@ton/sandbox";
import "@ton/test-utils";
import {
  SoulboundCollection,
  Mint,
  Transfer,
} from "../build/soulbound/soulbound_collection_SoulboundCollection";
import { SoulboundItem } from "../build/soulbound/soulbound_collection_SoulboundItem";

const COLLECTION_URI = "ipfs://unity-community/soulbound.json";
const BADGE_URI = "ipfs://unity-community/soulbound-1.json";

function offchainContent(uri: string): Cell {
  return beginCell().storeUint(0x01, 8).storeStringTail(uri).endCell();
}

describe("SoulboundCollection (TEP-85)", () => {
  let blockchain: Blockchain;
  let deployer: SandboxContract<TreasuryContract>;
  let recipient: SandboxContract<TreasuryContract>;
  let collection: SandboxContract<SoulboundCollection>;

  beforeEach(async () => {
    blockchain = await Blockchain.create();
    deployer = await blockchain.treasury("deployer");
    recipient = await blockchain.treasury("recipient");
    collection = blockchain.openContract(
      await SoulboundCollection.fromInit(deployer.address, offchainContent(COLLECTION_URI))
    );
  });

  async function mint(index: bigint, owner: Address) {
    return collection.send(
      deployer.getSender(),
      { value: toNano("0.15") },
      {
        $$type: "Mint",
        query_id: 0n,
        index,
        amount: toNano("0.1"),
        owner,
        common_content: offchainContent(BADGE_URI),
        forward_payload: EMPTY_CELL,
      } as Mint
    );
  }

  /**
   * Locate a minted item by replicating the collection's initOf computation.
   *
   * We intentionally do NOT use get_nft_address_by_index: like the reference
   * TEP-62/85 implementations, that getter builds the address with a
   * placeholder content cell, while the deployed item carries the real
   * per-mint content — so the two differ. Replicating fromInit with the known
   * content is the deterministic way to reach the actual deployed item.
   */
  async function openMintedItem(index: bigint, owner: Address) {
    const itemContent = beginCell()
      .storeUint(0x01, 8)
      .storeSlice(offchainContent(COLLECTION_URI).asSlice())
      .storeRef(offchainContent(BADGE_URI))
      .endCell();
    return blockchain.openContract(
      await SoulboundItem.fromInit(index, collection.address, owner, itemContent)
    );
  }

  it("mints a soulbound badge directly to the recipient", async () => {
    const tx = await mint(0n, recipient.address);

    expect(tx.transactions).toHaveTransaction({
      from: deployer.address,
      to: collection.address,
      success: true,
    });

    const item = await openMintedItem(0n, recipient.address);
    const nftData = await item.getGetNftData();
    expect(nftData.owner.equals(recipient.address)).toBe(true);
    expect(nftData.index).toBe(0n);
    expect((await collection.getGetCollectionData()).next_item_index).toBe(1n);
  });

  it("rejects any transfer of a soulbound badge", async () => {
    await mint(0n, recipient.address);
    const item = await openMintedItem(0n, recipient.address);

    const tx = await item.send(
      recipient.getSender(), // even the current owner cannot transfer
      { value: toNano("0.05") },
      {
        $$type: "Transfer",
        query_id: 0n,
        new_owner: recipient.address,
        response_destination: recipient.address,
        custom_payload: null,
        forward_amount: 0n,
        forward_payload: beginCell().endCell().asSlice(),
      } as Transfer
    );

    // Transfer fails with the SoulboundNotTransferable exit code (1020).
    const failedTx = tx.transactions.find(
      (t) =>
        t.description.type === "generic" &&
        t.description.computePhase.type === "vm" &&
        t.description.computePhase.exitCode === 1020
    );
    expect(failedTx).toBeDefined();

    // Ownership is unchanged.
    expect((await item.getGetNftData()).owner.equals(recipient.address)).toBe(true);
  });

  it("rejects a mint from a non-owner", async () => {
    const tx = await collection.send(
      recipient.getSender(),
      { value: toNano("0.15") },
      {
        $$type: "Mint",
        query_id: 0n,
        index: 0n,
        amount: toNano("0.1"),
        owner: recipient.address,
        common_content: offchainContent(BADGE_URI),
        forward_payload: EMPTY_CELL,
      } as Mint
    );

    expect(tx.transactions).toHaveTransaction({
      from: recipient.address,
      to: collection.address,
      success: false,
    });
  });
});
