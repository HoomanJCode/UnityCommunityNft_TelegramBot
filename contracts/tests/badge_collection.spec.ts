/**
 * Tests for the TEP-62 transferable badge collection (contracts/transferable/).
 *
 * The "raw body" test mirrors the exact mint body produced by the Python
 * client (backend/services/ton.py) to prove the two stay encoding-compatible.
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
  BadgeCollection,
  Mint,
  Transfer,
} from "../build/transferable/badge_collection_BadgeCollection";
import { BadgeItem } from "../build/transferable/badge_collection_BadgeItem";

const COLLECTION_URI = "ipfs://unity-community/collection.json";
const BADGE_URI = "ipfs://unity-community/badge-1.json";

function offchainContent(uri: string): Cell {
  return beginCell().storeUint(0x01, 8).storeStringTail(uri).endCell();
}

describe("BadgeCollection (TEP-62 transferable)", () => {
  let blockchain: Blockchain;
  let deployer: SandboxContract<TreasuryContract>;
  let recipient: SandboxContract<TreasuryContract>;
  let collection: SandboxContract<BadgeCollection>;

  beforeEach(async () => {
    blockchain = await Blockchain.create();
    deployer = await blockchain.treasury("deployer");
    recipient = await blockchain.treasury("recipient");
    // Deploy the collection up front (message with state init) so getters
    // work and mints can be observed in isolation.
    const contract = await BadgeCollection.fromInit(
      deployer.address,
      offchainContent(COLLECTION_URI)
    );
    collection = blockchain.openContract(contract);
    await deployer.send({
      to: contract.address,
      value: toNano("0.1"),
      init: contract.init,
      bounce: false,
    });
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
   * TEP-62 implementation, that getter builds the address with a placeholder
   * content cell, while the deployed item carries the real per-mint content —
   * so the two differ. Replicating fromInit with the known content is the
   * deterministic way to reach the actual deployed item.
   */
  async function openMintedItem(index: bigint, owner: Address) {
    const itemContent = beginCell()
      .storeUint(0x01, 8)
      .storeSlice(offchainContent(COLLECTION_URI).asSlice())
      .storeRef(offchainContent(BADGE_URI))
      .endCell();
    return blockchain.openContract(
      await BadgeItem.fromInit(index, collection.address, owner, itemContent)
    );
  }

  it("deploys and exposes the collection data", async () => {
    const data = await collection.getGetCollectionData();
    expect(data.owner.equals(deployer.address)).toBe(true);
    expect(data.next_item_index).toBe(0n);
  });

  it("mints a badge directly to the recipient", async () => {
    const tx = await mint(0n, recipient.address);

    expect(tx.transactions).toHaveTransaction({
      from: deployer.address,
      to: collection.address,
      success: true,
    });

    // Item index advanced.
    const data = await collection.getGetCollectionData();
    expect(data.next_item_index).toBe(1n);

    // The item was deployed at exactly the address the contract computes
    // (openMintedItem would throw if the get method hit an inactive contract).
    const item = await openMintedItem(0n, recipient.address);
    const nftData = await item.getGetNftData();
    expect(nftData.init_flag).toBe(0n);
    expect(nftData.index).toBe(0n);
    expect(nftData.collection.equals(collection.address)).toBe(true);
    expect(nftData.owner.equals(recipient.address)).toBe(true);
  });

  it("mints a badge from a raw body matching the Python client encoding", async () => {
    // Mirror of backend/services/ton.py PytoniqTONClient._build_mint_body.
    // @ton/core storeCoins and pytoniq store_coins both use TL-B var_uint16.
    const rawBody = beginCell()
      .storeUint(1, 32) // op: mint
      .storeUint(0n, 64) // query_id
      .storeUint(0n, 64) // index
      .storeCoins(toNano("0.1")) // amount
      .storeAddress(recipient.address) // owner
      .storeRef(offchainContent(BADGE_URI)) // common_content
      .storeRef(new Cell()) // forward_payload
      .endCell();

    // Treasury.send is the raw-message channel — same as a pytoniq wallet
    // transfer with a body.
    await deployer.send({ to: collection.address, value: toNano("0.15"), body: rawBody });

    const data = await collection.getGetCollectionData();
    expect(data.next_item_index).toBe(1n);

    const item = await openMintedItem(0n, recipient.address);
    const nftData = await item.getGetNftData();
    expect(nftData.owner.equals(recipient.address)).toBe(true);
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

  it("rejects a mint with the wrong item index", async () => {
    const tx = await mint(5n, recipient.address);

    expect(tx.transactions).toHaveTransaction({
      from: deployer.address,
      to: collection.address,
      success: false,
    });
    // Nothing was minted.
    expect((await collection.getGetCollectionData()).next_item_index).toBe(0n);
  });

  it("transfers a badge to a new owner", async () => {
    await mint(0n, recipient.address);
    const item = await openMintedItem(0n, recipient.address);
    const newOwner = await blockchain.treasury("new-owner");

    const tx = await item.send(
      recipient.getSender(), // current owner
      { value: toNano("0.05") },
      {
        $$type: "Transfer",
        query_id: 0n,
        new_owner: newOwner.address,
        response_destination: deployer.address,
        custom_payload: null,
        forward_amount: 0n,
        forward_payload: beginCell().endCell().asSlice(),
      } as Transfer
    );

    expect(tx.transactions).toHaveTransaction({
      from: recipient.address,
      to: item.address,
      success: true,
    });
    expect((await item.getGetNftData()).owner.equals(newOwner.address)).toBe(true);
  });

  it("rejects a transfer from a non-owner", async () => {
    await mint(0n, recipient.address);
    const item = await openMintedItem(0n, recipient.address);
    const attacker = await blockchain.treasury("attacker");

    const tx = await item.send(
      attacker.getSender(),
      { value: toNano("0.05") },
      {
        $$type: "Transfer",
        query_id: 0n,
        new_owner: attacker.address,
        response_destination: attacker.address,
        custom_payload: null,
        forward_amount: 0n,
        forward_payload: beginCell().endCell().asSlice(),
      } as Transfer
    );

    expect(tx.transactions).toHaveTransaction({
      from: attacker.address,
      to: item.address,
      success: false,
    });
    // Ownership is unchanged.
    expect((await item.getGetNftData()).owner.equals(recipient.address)).toBe(true);
  });
});
